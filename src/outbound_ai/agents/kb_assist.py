"""Knowledge-base assistant for human agents."""

from __future__ import annotations

import logging
import string
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from uuid import UUID

from outbound_ai.common.arabic import normalize_arabic
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
from outbound_ai.rag.embeddings import EmbeddingPort, build_embeddings, vector_literal

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


def _embedding_provider(settings: Settings) -> EmbeddingPort:
    return build_embeddings(settings)


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


_COMMON_QUERY_WORDS = {
    "من", "ما", "ماذا", "هل", "هو", "هي", "في", "عن", "على", "الى", "إلى",
    "هذا", "هذه", "ذلك", "تلك", "تم", "كان", "يكون", "الذي", "التي", "و", "or",
    "the", "what", "who", "where", "when", "how",
}
_TOKEN_TRIM = string.punctuation + "،؛؟"


def _content_terms(text: str) -> set[str]:
    terms: set[str] = set()
    for raw_token in normalize_arabic(text).lower().split():
        token = raw_token.strip(_TOKEN_TRIM)
        if len(token) >= 3 and token not in _COMMON_QUERY_WORDS:
            terms.add(token)
    return terms


def _has_query_support(query_terms: set[str], content_terms: set[str]) -> bool:
    """Support exact, Arabic-normalized, and small-typo matches."""

    if not query_terms or not content_terms:
        return False
    if query_terms & content_terms:
        return True
    return any(
        SequenceMatcher(None, query_term, content_term).ratio() >= 0.82
        for query_term in query_terms
        for content_term in content_terms
    )


def _select_relevant_matches(
    matches: list[KnowledgeMatch],
    settings: Settings,
    query_text: str,
) -> list[KnowledgeMatch]:
    """Keep strong and query-supported evidence, not arbitrary top-k rows.

    The hybrid score ranks candidates but is not a calibrated probability. A
    fixed floor, a score-gap rule, and a lightweight lexical-support check are
    combined so a genuinely multi-source answer can retain several documents,
    while an unrelated tail result is excluded even when the database returns
    it in the requested top-k window.
    """

    if not matches:
        return []
    ranked = sorted(matches, key=lambda item: item.similarity, reverse=True)
    top_score = ranked[0].similarity
    floor = max(
        settings.rag_min_citation_score,
        top_score * settings.rag_citation_relative_threshold,
    )
    max_unmatched_gap = max(0.12, top_score * 0.25)
    lexical_min_score = max(0.15, settings.rag_min_citation_score * 0.5)
    query_terms = _content_terms(query_text)
    # Greetings, very short inputs, and punctuation-only inputs have no
    # document-search intent. Never turn arbitrary top-k rows into sources.
    if not query_terms:
        return []
    support_by_match = {
        id(match): _has_query_support(query_terms, _content_terms(match.content_raw))
        for match in ranked
    }
    if not any(
        support_by_match[id(match)] and match.similarity >= lexical_min_score
        for match in ranked
    ) and top_score < settings.rag_min_grounding_score:
        return []
    selected: list[KnowledgeMatch] = []
    for index, match in enumerate(ranked):
        lexical_support = support_by_match[id(match)]
        # Explicit normalized/typo-tolerant lexical evidence can qualify a
        # result even when its semantic score falls below the relative floor.
        if lexical_support and match.similarity >= lexical_min_score:
            selected.append(match)
            continue
        if match.similarity < floor:
            continue
        if index == 0:
            selected.append(match)
            continue
        score_gap = top_score - match.similarity
        if score_gap > max_unmatched_gap:
            continue
        selected.append(match)
    return selected[: settings.rag_max_citations]


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
        "إذا كان السؤال مختصراً أو حذف اسم الدولة أو الجهة، أكمل الإجابة بسياقها الكامل كما يظهر في الدليل؛ "
        "لا تكتفِ بإجابة مبتورة مثل اسم شخص فقط. ضع أرقام المصادر مثل [S1] بعد الجمل التي تعتمد عليها.\n\n"
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
    normalized_question = normalize_arabic(question)
    embedding_query = question
    if normalized_question and normalized_question != question:
        embedding_query = f"{question}\n{normalized_question}"
    query_vector = embeddings.embed([embedding_query])[0]
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
            query_text=normalized_question or question,
            query_embedding=vector_literal(query_vector),
            # Retrieve a wider candidate set, then filter the tail before the
            # LLM sees it. This improves recall without presenting weak sources.
            match_count=max(settings.rag_top_n_after_rerank * 4, settings.rag_max_citations),
        )
        selected_matches = _select_relevant_matches(matches, settings, question)
        citations = _citation_rows(selected_matches)
        grounded = bool(citations) and citations[0].similarity >= settings.rag_min_grounding_score
        # The hybrid score is a ranking indicator, not a calibrated probability.
        # The selected citations are the only evidence passed to the LLM; the
        # offline template is reserved for no evidence or explicit offline mode.
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
