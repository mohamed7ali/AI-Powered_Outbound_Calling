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
_RESOLVED = ("نعم", "ايوه", "تمام", "خلاص", "اتحلت", "تحلت")
_UNRESOLVED = ("لا", "لسه", "مشكله", "ماتحلتش", "لم تحل", "غير متاكد")
_TOKEN_RE = re.compile(r"[^\W_]+", flags=re.UNICODE)


def _contains_phrase(normalized: str, phrase: str) -> bool:
    """Match a normalized Arabic word or phrase on token boundaries."""

    text_tokens = _TOKEN_RE.findall(normalized)
    phrase_tokens = _TOKEN_RE.findall(phrase)
    if not phrase_tokens:
        return False
    width = len(phrase_tokens)
    return any(text_tokens[index : index + width] == phrase_tokens for index in range(len(text_tokens) - width + 1))


def _contains_any(normalized: str, phrases: tuple[str, ...]) -> bool:
    return any(_contains_phrase(normalized, phrase) for phrase in phrases)


def decide_follow_up(*, digits: str = "", speech: str = "", answered: bool = True) -> FollowUpDecision:
    """The call ends after capture; HUMAN_TASK means create a post-call task.

    Unresolved signals intentionally take precedence over resolved signals. A
    response such as ``المشكلة اتحلت بس لسه فيه حاجة`` must not be classified as
    resolved merely because it contains an earlier positive phrase.
    """

    if not answered:
        return FollowUpDecision(FollowUpAction.NO_ANSWER, "customer_did_not_answer")
    normalized = normalize_arabic(speech)
    if digits in {"0", "2"} or _contains_any(normalized, _UNRESOLVED):
        return FollowUpDecision(FollowUpAction.HUMAN_TASK, "customer_needs_human_follow_up")
    if digits == "1" or _contains_any(normalized, _RESOLVED):
        return FollowUpDecision(FollowUpAction.RESOLVED, "customer_confirmed_resolution")
    return FollowUpDecision(FollowUpAction.HUMAN_TASK, "ambiguous_customer_answer")


__all__ = ["FollowUpAction", "FollowUpDecision", "decide_follow_up"]
