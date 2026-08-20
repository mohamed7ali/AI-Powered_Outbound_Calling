"""Offline tests for the RAG and agent integration seams."""

from __future__ import annotations

import logging
from uuid import uuid4

from outbound_ai.agents.kb_assist import Citation
from outbound_ai.common.arabic import normalize_arabic
from outbound_ai.observability.logging import log_event
from outbound_ai.rag.chunking import chunk_text
from outbound_ai.rag.embeddings import DeterministicEmbeddings, vector_literal


def test_arabic_normalization_supports_retrieval_variants() -> None:
    assert normalize_arabic("أيوة، المشكلة اتحلّت ١٢٣") == "ايوه, المشكله اتحلت 123"


def test_chunking_preserves_raw_and_normalized_forms() -> None:
    chunks = chunk_text("أهلاً. هذه مشكلة مهمة. نحتاج متابعة.", max_characters=200)
    assert chunks
    assert chunks[0].content_raw
    assert chunks[0].content_norm
    assert chunks[0].index == 0


def test_embedding_dimension_and_pgvector_literal() -> None:
    vector = DeterministicEmbeddings(3072).embed(["مساعدة"])[0]
    literal = vector_literal(vector)
    assert len(vector) == 3072
    assert literal.startswith("[") and literal.endswith("]")


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
