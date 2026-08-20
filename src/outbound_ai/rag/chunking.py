"""Arabic-friendly chunking for knowledge documents."""

from __future__ import annotations

from dataclasses import dataclass

from outbound_ai.common.arabic import normalize_arabic, normalize_light


@dataclass(frozen=True, slots=True)
class TextChunk:
    index: int
    content_raw: str
    content_norm: str
    page_number: int | None = None


def _sentences(text: str) -> list[str]:
    """Split on Arabic and Latin sentence boundaries without destroying content."""
    parts: list[str] = []
    current: list[str] = []
    for character in text:
        current.append(character)
        if character in ".!?؟؛\n":
            value = normalize_light("".join(current))
            if value:
                parts.append(value)
            current = []
    tail = normalize_light("".join(current))
    if tail:
        parts.append(tail)
    return parts


def chunk_text(
    text: str,
    *,
    max_characters: int = 1200,
    overlap_characters: int = 180,
    page_number: int | None = None,
) -> list[TextChunk]:
    """Create overlapping chunks while retaining Arabic raw and normalized forms."""

    if max_characters < 200:
        raise ValueError("max_characters must be at least 200")
    if not 0 <= overlap_characters < max_characters:
        raise ValueError("overlap_characters must be between 0 and max_characters")

    sentences = _sentences(text)
    chunks: list[TextChunk] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip()
        if current and len(candidate) > max_characters:
            raw = normalize_light(current)
            chunks.append(
                TextChunk(
                    index=len(chunks),
                    content_raw=raw,
                    content_norm=normalize_arabic(raw),
                    page_number=page_number,
                )
            )
            overlap = raw[-overlap_characters:] if overlap_characters else ""
            current = f"{overlap} {sentence}".strip()
        else:
            current = candidate

    if current:
        raw = normalize_light(current)
        chunks.append(
            TextChunk(
                index=len(chunks),
                content_raw=raw,
                content_norm=normalize_arabic(raw),
                page_number=page_number,
            )
        )
    return chunks
