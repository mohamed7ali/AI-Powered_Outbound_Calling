"""Offline tests for the RAG and agent integration seams."""

from __future__ import annotations

import logging
import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest

from outbound_ai.agents.kb_assist import Citation, _select_relevant_matches
from outbound_ai.common.arabic import normalize_arabic
from outbound_ai.observability.logging import log_event
from outbound_ai.rag.chunking import chunk_text
from outbound_ai.config.settings import Settings
from outbound_ai.db.repositories.knowledge import KnowledgeMatch
from outbound_ai.rag.embeddings import (
    DeterministicEmbeddings,
    SentenceTransformerEmbeddings,
    build_embeddings,
    clear_embedding_cache,
    vector_literal,
)


def test_arabic_normalization_supports_retrieval_variants() -> None:
    assert normalize_arabic("أيوة، المشكلة اتحلّت ١٢٣") == "ايوه, المشكله اتحلت 123"


def test_chunking_preserves_raw_and_normalized_forms() -> None:
    chunks = chunk_text("أهلاً. هذه مشكلة مهمة. نحتاج متابعة.", max_characters=200)
    assert chunks
    assert chunks[0].content_raw
    assert chunks[0].content_norm
    assert chunks[0].index == 0


def test_embedding_dimension_and_pgvector_literal() -> None:
    vector = DeterministicEmbeddings(384).embed(["مساعدة"])[0]
    literal = vector_literal(vector)
    assert len(vector) == 384
    assert literal.startswith("[") and literal.endswith("]")


def test_sentence_transformer_adapter_is_lazy_and_dimension_checked(monkeypatch) -> None:
    class FakeModel:
        def __init__(self, name, device, trust_remote_code):
            assert name == "fake-arabic-model"
            assert device == "cpu"
            assert trust_remote_code is False

        def get_sentence_embedding_dimension(self):
            return 3

        def encode(self, texts, **kwargs):
            assert texts == ["مساعدة"]
            assert kwargs["normalize_embeddings"] is True
            return [[0.1, 0.2, 0.3]]

    monkeypatch.setitem(sys.modules, "sentence_transformers", SimpleNamespace(SentenceTransformer=FakeModel))
    settings = Settings(
        rag_embedding_provider="sentence_transformers",
        rag_embedding_dim=3,
        sentence_transformer_model="fake-arabic-model",
    )
    provider = SentenceTransformerEmbeddings(settings)
    assert provider.dimension == 3
    assert provider.embed(["مساعدة"]) == [[0.1, 0.2, 0.3]]


def test_sentence_transformer_provider_is_cached(monkeypatch) -> None:
    calls = 0

    class CachedModel:
        def __init__(self, *args, **kwargs):
            nonlocal calls
            calls += 1

        def get_sentence_embedding_dimension(self):
            return 384

        def encode(self, texts, **kwargs):
            return [[0.0] * 384 for _ in texts]

    monkeypatch.setitem(sys.modules, "sentence_transformers", SimpleNamespace(SentenceTransformer=CachedModel))
    clear_embedding_cache()
    settings = Settings(
        rag_embedding_provider="sentence_transformers",
        rag_embedding_dim=384,
        sentence_transformer_model="cached-arabic-model",
    )
    first = build_embeddings(settings)
    second = build_embeddings(settings)
    assert first is second
    assert calls == 1
    clear_embedding_cache()


def test_sentence_transformer_adapter_rejects_wrong_model_dimension(monkeypatch) -> None:
    class WrongDimensionModel:
        def __init__(self, *args, **kwargs):
            pass

        def get_sentence_embedding_dimension(self):
            return 768

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        SimpleNamespace(SentenceTransformer=WrongDimensionModel),
    )
    settings = Settings(
        rag_embedding_provider="sentence_transformers",
        rag_embedding_dim=384,
        sentence_transformer_model="fake-arabic-model",
    )
    with pytest.raises(ValueError, match="returns 768 dimensions"):
        SentenceTransformerEmbeddings(settings)


def test_weak_tail_matches_are_not_returned_as_citations() -> None:
    def match(score: float) -> KnowledgeMatch:
        return KnowledgeMatch(
            id=uuid4(),
            document_id=uuid4(),
            organization_id=uuid4(),
            document_title="دليل الدعم",
            storage_path=None,
            content_raw="نص المصدر",
            page_number=None,
            similarity=score,
        )

    settings = Settings(
        rag_embedding_provider="deterministic",
        rag_min_citation_score=0.30,
        rag_citation_relative_threshold=0.55,
        rag_max_citations=3,
    )
    selected = _select_relevant_matches(
        [
            KnowledgeMatch(
                id=uuid4(),
                document_id=uuid4(),
                organization_id=uuid4(),
                document_title="دليل الدعم",
                storage_path=None,
                content_raw="سؤال عن الدعم",
                page_number=None,
                similarity=0.80,
            ),
            match(0.50),
            match(0.2079),
        ],
        settings,
        "سؤال عن الدعم",
    )
    assert [item.similarity for item in selected] == [0.80]


def test_exact_reported_arabic_question_accepts_matching_source() -> None:
    source = KnowledgeMatch(
        id=uuid4(),
        document_id=uuid4(),
        organization_id=uuid4(),
        document_title="اختبار",
        storage_path=None,
        content_raw="محمد صلاح يلعب في الإنتاج الحربي عمر مرموش هو رئيس جمهورية الحب جالي",
        page_number=None,
        similarity=0.555,
    )
    unrelated = KnowledgeMatch(
        id=uuid4(),
        document_id=uuid4(),
        organization_id=uuid4(),
        document_title="اختبار ثان",
        storage_path=None,
        content_raw="عاصمة مصر هي روما",
        page_number=None,
        similarity=0.359,
    )
    settings = Settings(
        rag_embedding_provider="deterministic",
        rag_min_citation_score=0.30,
        rag_citation_relative_threshold=0.75,
        rag_max_citations=3,
    )
    selected = _select_relevant_matches(
        [source, unrelated],
        settings,
        "مين رئيس جمهورية الحب جالي؟",
    )
    assert [item.document_title for item in selected] == ["اختبار"]


def test_greeting_or_unrelated_question_returns_no_sources() -> None:
    def match(score: float) -> KnowledgeMatch:
        return KnowledgeMatch(
            id=uuid4(),
            document_id=uuid4(),
            organization_id=uuid4(),
            document_title="اختبار",
            storage_path=None,
            content_raw="معلومة لا تخص التحية",
            page_number=None,
            similarity=score,
        )

    settings = Settings(
        rag_embedding_provider="deterministic",
        rag_min_citation_score=0.30,
        rag_citation_relative_threshold=0.75,
        rag_max_citations=3,
    )
    assert _select_relevant_matches([match(0.80)], settings, "hi") == []
    assert _select_relevant_matches([match(0.55)], settings, "ما هو سعر الطقس؟") == []


def test_reported_irrelevant_arabic_tail_document_is_removed() -> None:
    def match(score: float, content: str) -> KnowledgeMatch:
        return KnowledgeMatch(
            id=uuid4(),
            document_id=uuid4(),
            organization_id=uuid4(),
            document_title="اختبار",
            storage_path=None,
            content_raw=content,
            page_number=None,
            similarity=score,
        )

    settings = Settings(
        rag_embedding_provider="deterministic",
        rag_min_citation_score=0.30,
        rag_citation_relative_threshold=0.75,
        rag_max_citations=3,
    )
    selected = _select_relevant_matches(
        [
            match(0.555, "محمد صلاح يلعب في الإنتاج الحربي عمر مرموش هو رئيس جمهورية الحب"),
            match(0.359, "عاصمة مصر هي روما"),
        ],
        settings,
        "من هو رئيس جمهورية الحب؟",
    )
    assert [item.similarity for item in selected] == [0.555]


def test_query_supported_multiple_documents_are_retained() -> None:
    def match(score: float, content: str) -> KnowledgeMatch:
        return KnowledgeMatch(
            id=uuid4(),
            document_id=uuid4(),
            organization_id=uuid4(),
            document_title="دليل الدعم",
            storage_path=None,
            content_raw=content,
            page_number=None,
            similarity=score,
        )

    settings = Settings(
        rag_embedding_provider="deterministic",
        rag_min_citation_score=0.30,
        rag_citation_relative_threshold=0.55,
        rag_max_citations=3,
    )
    selected = _select_relevant_matches(
        [
            match(0.80, "محمد صلاح يلعب في ليفربول"),
            match(0.55, "محمد صلاح انتقل إلى فريق آخر"),
            match(0.50, "الطقس في القاهرة اليوم"),
        ],
        settings,
        "أين يلعب محمد صلاح وما آخر انتقال له؟",
    )
    assert [item.similarity for item in selected] == [0.80, 0.55]


def test_citations_are_json_safe_and_do_not_expose_full_document() -> None:
    citation = Citation(
        citation_id="S1",
        chunk_id=uuid4(),
        document_id=uuid4(),
        page_number=2,
        similarity=0.91,
        quote="نص المصدر",
    )
    value = citation.as_dict()
    assert isinstance(value["chunk_id"], str)
    assert value["quote"] == "نص المصدر"


def test_logging_redacts_sensitive_values(caplog) -> None:
    logger = logging.getLogger("rag-test")
    with caplog.at_level(logging.INFO):
        log_event(logger, "query", phone_e164="+201000000000", content="نص خاص")
    assert "+201000000000" not in caplog.text
    assert "نص خاص" not in caplog.text
    assert "REDACTED" in caplog.text
