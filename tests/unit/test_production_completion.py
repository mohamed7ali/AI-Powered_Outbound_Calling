from __future__ import annotations

from uuid import uuid4

import pytest

from outbound_ai.reports.service import calculate_fcr_metrics
from outbound_ai.telephony.routing import FollowUpAction, decide_follow_up


def test_routing_resolved_and_unresolved_are_post_call_actions() -> None:
    assert decide_follow_up(digits="1").action is FollowUpAction.RESOLVED
    assert decide_follow_up(speech="لسه المشكلة موجودة").action is FollowUpAction.HUMAN_TASK
    assert decide_follow_up(speech="مش فاكر").action is FollowUpAction.HUMAN_TASK
    assert decide_follow_up(answered=False).action is FollowUpAction.NO_ANSWER


def test_routing_does_not_treat_arabic_substrings_as_answers() -> None:
    assert decide_follow_up(speech="أهلاً وسهلاً").action is FollowUpAction.HUMAN_TASK


def test_unresolved_signal_wins_over_earlier_resolved_signal() -> None:
    decision = decide_follow_up(speech="المشكلة اتحلت بس لسه فيه حاجة صغيرة")
    assert decision.action is FollowUpAction.HUMAN_TASK


def test_fcr_metrics_are_zero_safe() -> None:
    assert calculate_fcr_metrics(total_calls=0, answered_calls=0, resolved_calls=0) == (0.0, 0.0)
    assert calculate_fcr_metrics(total_calls=10, answered_calls=8, resolved_calls=4) == (0.8, 0.5)


def test_fcr_metrics_reject_negative_counts() -> None:
    with pytest.raises(ValueError):
        calculate_fcr_metrics(total_calls=-1, answered_calls=0, resolved_calls=0)
