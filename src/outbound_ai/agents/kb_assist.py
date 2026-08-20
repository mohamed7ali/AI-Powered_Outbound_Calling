"""Knowledge-base assistant for human agents."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from uuid import UUID

from outbound_ai.config.settings import Settings, get_settings
from outbound_ai.db.connection import TenantContext, get_database
from outbound_ai.db.repositories.agent import (
    append_message,
    create_conversation,
    conversation_belongs_to_actor,
    write_audit_event,
)
from outbound_ai.db.repositories.knowledge import KnowledgeMatch, hybrid_match_chunks
from outbound_ai.observability.logging import log_event
from outbound_ai.rag.embeddings import DeterministicEmbeddings, OpenAIEmbeddings, vector_literal

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Citation:
    citation_id: str
    chunk_id: UUID
    document_id: UUID
    page_number: int | None
    similarity: float
    quote: str
    document_title: str = "مستند المؤسسة"
    storage_path: str | None = None

    def as_dict(self) -> dict:
        value = asdict(self)
        value["chunk_id"] = str(self.chunk_id)
        value["document_id"] = str(self.document_id)
        return value


@dataclass(frozen=True, slots=True)
class AgentAnswer:
    conversation_id: UUID
    answer: str
    citations: list[Citation]
    grounded: bool
    used_llm: bool


def _embedding_provider(settings: Settings):
    if settings.rag_embedding_provider == "deterministic":
        return DeterministicEmbeddings(settings.openai_embedding_dim)
    return OpenAIEmbeddings(settings)


def _citation_rows(matches: list[KnowledgeMatch]) -> list[Citation]:
    return [
        Citation(
            citation_id=f"S{index}",
            chunk_id=match.id,
            document_id=match.document_id,
            document_title=match.document_title,
            storage_path=match.storage_path,
            page_number=match.page_number,
            similarity=round(match.similarity, 4),
            quote=match.content_raw[:360],
        )
        for index, match in enumerate(matches, start=1)
    ]


def _offline_answer(citations: list[Citation]) -> str:
    if not citations:
        return "لم أجد إجابة موثقة في مستندات المؤسسة الحالية. من فضلك صعّد السؤال لموظف مختص."
    return (
        "وجدت معلومات مرتبطة في قاعدة معرفة المؤسسة. راجع المصادر التالية قبل تقديم الرد للعميل: "
        + ", ".join(citation.citation_id for citation in citations)
        + ". هذا رد تجريبي لأن نموذج اللغة غير مفعّل حالياً."
    )


def _llm_answer(settings: Settings, question: str, citations: list[Citation]) -> str:
    """Generate a grounded answer through the selected provider, or fall back offline."""

    if settings.llm_provider == "offline":
        return _offline_answer(citations)

    api_key = None
    model = ""
    base_url = None
    if settings.llm_provider == "gemini" and settings.gemini_api_key:
        api_key = settings.gemini_api_key.get_secret_value()
        model = settings.gemini_model
        base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
    elif settings.llm_provider == "openai" and settings.openai_api_key:
        api_key = settings.openai_api_key.get_secret_value()
        model = settings.openai_call_model
    else:
        return _offline_answer(citations)

    from openai import OpenAI

    evidence = "\n\n".join(
        f"[{citation.citation_id}] {citation.quote}" for citation in citations
    )
    prompt = (
        "أنت مساعد لموظف خدمة عملاء. أجب بالعربية الواضحة وباختصار. "
        "استخدم الأدلة فقط، ولا تخترع سياسة أو معلومة. إذا لم تكف الأدلة فقل ذلك بوضوح. "
        "ضع أرقام المصادر مثل [S1] بعد الجمل التي تعتمد عليها.\n\n"
        f"السؤال: {question}\n\nالأدلة:\n{evidence}"
    )
    client_kwargs = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url
    client = OpenAI(**client_kwargs)
    response = client.chat.completions.create(
        model=model,
        temperature=0.1,
        messages=[
            {"role": "system", "content": "أنت مساعد معرفة مؤسسية ملتزم بالمصادر."},
            {"role": "user", "content": prompt},
        ],
    )
    return (response.choices[0].message.content or _offline_answer(citations)).strip()


def _llm_enabled(settings: Settings) -> bool:
    return (
        (settings.llm_provider == "openai" and settings.openai_api_key is not None)
        or (settings.llm_provider == "gemini" and settings.gemini_api_key is not None)
    )


def answer_question(
    *,
    context: TenantContext,
    question: str,
    conversation_id: UUID | None = None,
    settings: Settings | None = None,
    embeddings=None,
) -> AgentAnswer:
    """Answer only from the authenticated organization’s knowledge base."""

    if context.organization_id is None or context.actor_id is None:
        raise ValueError("RAG requires both actor and organization context")
    if not question.strip():
        raise ValueError("question cannot be empty")
    settings = settings or get_settings()
    embeddings = embeddings or _embedding_provider(settings)
    query_vector = embeddings.embed([question])[0]
    database = get_database()

    with database.transaction(context) as connection:
        if conversation_id is None:
            conversation_id = create_conversation(
                connection,
                organization_id=context.organization_id,
                user_id=context.actor_id,
                title=question[:120],
            )
        elif not conversation_belongs_to_actor(
            connection,
            conversation_id=conversation_id,
            organization_id=context.organization_id,
            user_id=context.actor_id,
        ):
            raise PermissionError("Conversation does not belong to the authenticated actor")

        matches = hybrid_match_chunks(
            connection,
            context=context,
            query_text=question,
            query_embedding=vector_literal(query_vector),
            match_count=settings.rag_top_n_after_rerank,
        )
        citations = _citation_rows(matches)
        grounded = bool(citations) and citations[0].similarity >= settings.rag_min_grounding_score
        if not grounded:
            citations = citations[:3]
        # Deterministic embeddings can produce a lower numeric similarity even
        # when lexical/hybrid retrieval found useful evidence. If citations exist
        # and a provider is configured, let the provider answer strictly from
        # those citations; reserve the offline template for no evidence or an
        # explicitly offline configuration.
        answer = (
            _llm_answer(settings, question, citations)
            if citations and _llm_enabled(settings)
            else _offline_answer(citations)
        )
        append_message(
            connection,
            organization_id=context.organization_id,
            conversation_id=conversation_id,
            role="user",
            content=question,
        )
        append_message(
            connection,
            organization_id=context.organization_id,
            conversation_id=conversation_id,
            role="assistant",
            content=answer,
            citations=[citation.as_dict() for citation in citations],
        )
        try:
            # Keep audit logging in a savepoint. A missing/outdated audit_events
            # RLS policy must not roll back the already-generated answer and chat
            # messages; the migration still needs to be applied in Supabase.
            with connection.transaction():
                write_audit_event(
                    connection,
                    organization_id=context.organization_id,
                    actor_id=context.actor_id,
                    event_type="KNOWLEDGE_QUERY",
                    resource_type="agent_conversation",
                    resource_id=conversation_id,
                    metadata={
                        "citation_count": len(citations),
                        "grounded": grounded,
                        "used_llm": _llm_enabled(settings),
                        "llm_provider": settings.llm_provider,
                    },
                )
        except Exception as exc:
            logger.warning(
                "audit_event_write_failed_answer_preserved",
                extra={"error_type": type(exc).__name__, "organization_id": str(context.organization_id)},
            )
    log_event(
        logger,
        "agent_answered",
        organization_id=str(context.organization_id),
        actor_id=str(context.actor_id),
        conversation_id=str(conversation_id),
        citation_count=len(citations),
        grounded=grounded,
    )
    return AgentAnswer(
        conversation_id=conversation_id,
        answer=answer,
        citations=citations,
        grounded=grounded,
        used_llm=_llm_enabled(settings),
    )
