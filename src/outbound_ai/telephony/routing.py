"""Post-call decision policy for the Arabic follow-up workflow."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from outbound_ai.common.arabic import normalize_arabic


class FollowUpAction(StrEnum):
    RESOLVED = "RESOLVED"
    HUMAN_TASK = "HUMAN_TASK"
    RETRY = "RETRY"
    NO_ANSWER = "NO_ANSWER"


@dataclass(frozen=True, slots=True)
class FollowUpDecision:
    action: FollowUpAction
    reason: str


# Terms are matched as complete Arabic word tokens, not substrings. This prevents
# `لا` from matching the final letters of `اهلا`, for example.
_RESOLVED = (
    "نعم", "ايوه", "ايوا", "اه", "أجل", "اجل", "بلى", "بلي", "تمام", "خلاص",
    "اتحلت", "تحلت", "حلت", "انحلت", "اتصلحت", "تم حلها", "تم حل المشكلة",
    "قد حلت", "انتهت المشكلة", "تم إصلاحها", "تم اصلاحها", "المشكلة تعمل",
    "الخدمة تعمل",
)
_UNRESOLVED = (
    "لا", "لسه", "ماتحلتش", "ما اتحلت", "ما انحلت", "مازالت",
    "لم تحل", "لم تُحل", "لم تنحل", "لم تنته", "لم تتم المعالجة",
    "لم يتم حلها", "ما زالت", "لا تزال", "المشكلة قائمة", "المشكلة موجودة",
    "ما تحليت", "ما اتحلتش",
    "لسه موجودة", "تحتاج متابعة", "تحتاج إلى متابعة", "غير محلولة",
    "غير متاكد", "غير متأكد",
)
_TOKEN_RE = re.compile(r"[^\W_]+", flags=re.UNICODE)
_PROBLEM_WORDS = {"مشكله", "المشكله"}
# These are recurring faster-whisper substitutions observed in the customer
# rows: `حالة/حالت/حلطه` instead of a form of `حُلّت/اتحلت`.
_MISHEARD_RESOLVED_WORDS = {"حاله", "حالت", "حلطه", "حلطت"}
_STRONG_MISHEARD_RESOLVED_WORDS = {"حلطه", "حلطت"}
_AFFIRMATIVE_CONTEXT_WORDS = {"تم", "نعم", "ايوه", "ايوا", "اه", "طبعا", "اوه"}


def _contains_phrase(normalized: str, phrase: str) -> bool:
    """Match a normalized Arabic word or phrase on token boundaries."""

    text_tokens = _TOKEN_RE.findall(normalize_arabic(normalized))
    # Normalize the phrase as well as the transcript. Without this, a phrase
    # such as `المشكلة حُلّت` could fail after the input was normalized to
    # `المشكله حلت`, causing a valid affirmative answer to become unclear.
    phrase_tokens = _TOKEN_RE.findall(normalize_arabic(phrase))
    if not phrase_tokens:
        return False
    width = len(phrase_tokens)
    return any(text_tokens[index : index + width] == phrase_tokens for index in range(len(text_tokens) - width + 1))


def _contains_any(normalized: str, phrases: tuple[str, ...]) -> bool:
    return any(_contains_phrase(normalized, phrase) for phrase in phrases)


def _contains_contextual_misheard_resolved(normalized: str) -> bool:
    """Recognize recurring Whisper errors only with resolution context.

    A bare `حالة المشكلة` is ambiguous and must not resolve a case. The noisy
    forms observed in the saved call transcripts become actionable only when
    Whisper also captured an affirmative marker such as `تم` or `طبعا`.
    """
    tokens = set(_TOKEN_RE.findall(normalize_arabic(normalized)))
    has_problem = bool(tokens & _PROBLEM_WORDS)
    has_misheard = bool(tokens & _MISHEARD_RESOLVED_WORDS)
    has_strong_misheard = bool(tokens & _STRONG_MISHEARD_RESOLVED_WORDS)
    has_affirmative_context = bool(tokens & _AFFIRMATIVE_CONTEXT_WORDS)
    return has_problem and has_misheard and (has_strong_misheard or has_affirmative_context)


def decide_follow_up(*, digits: str = "", speech: str = "", answered: bool = True) -> FollowUpDecision:
    """The call ends after capture; HUMAN_TASK means create a post-call task.

    Unresolved signals intentionally take precedence over resolved signals. A
    response such as ``المشكلة اتحلت بس لسه فيه حاجة`` must not be classified as
    resolved merely because it contains an earlier positive phrase.
    """

    if not answered:
        return FollowUpDecision(FollowUpAction.NO_ANSWER, "لم يرد العميل على المكالمة")
    normalized = normalize_arabic(speech)
    if digits in {"0", "2"} or _contains_any(normalized, _UNRESOLVED):
        return FollowUpDecision(FollowUpAction.HUMAN_TASK, "العميل أفاد بأن المشكلة ما زالت قائمة وتحتاج إلى متابعة من موظف خدمة العملاء")
    if digits == "1" or _contains_any(normalized, _RESOLVED) or _contains_contextual_misheard_resolved(normalized):
        return FollowUpDecision(FollowUpAction.RESOLVED, "العميل أكد أن المشكلة تم حلها")
    if not digits.strip() and not speech.strip():
        return FollowUpDecision(
            FollowUpAction.HUMAN_TASK,
            "لم نتلقَّ رداً صوتياً من العميل أثناء فترة الاستماع؛ يلزم التحقق والمتابعة من موظف خدمة العملاء",
        )
    return FollowUpDecision(FollowUpAction.HUMAN_TASK, "إجابة العميل غير واضحة؛ يلزم التحقق والمتابعة من موظف خدمة العملاء")


__all__ = ["FollowUpAction", "FollowUpDecision", "decide_follow_up"]
