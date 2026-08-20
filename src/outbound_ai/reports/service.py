"""Organization-scoped FCR reporting service."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from outbound_ai.db.connection import TenantContext, get_database


@dataclass(frozen=True, slots=True)
class FcrReport:
    organization_id: UUID
    period_start: date
    period_end: date
    total_calls: int
    resolved_on_first_follow_up: int
    escalated_calls: int
    answer_rate: float
    fcr_rate: float
    average_duration_seconds: float
    report_text: str


def calculate_fcr_metrics(*, total_calls: int, answered_calls: int, resolved_calls: int) -> tuple[float, float]:
    """Return answer and first-call-resolution rates with zero-safe denominators."""

    if min(total_calls, answered_calls, resolved_calls) < 0:
        raise ValueError("FCR counts cannot be negative")
    answer_rate = answered_calls / total_calls if total_calls else 0.0
    fcr_rate = resolved_calls / answered_calls if answered_calls else 0.0
    return answer_rate, fcr_rate


def generate_fcr_report(
    *,
    context: TenantContext,
    period_start: date,
    period_end: date,
) -> FcrReport:
    """Aggregate only the active organization’s calls and upsert its report."""

    if context.organization_id is None:
        raise ValueError("An organization context is required")
    if period_end < period_start:
        raise ValueError("period_end must not precede period_start")
    database = get_database()
    with database.transaction(context) as connection:
        row = connection.execute(
            """
            with scoped as (
              select outcome, status, duration_seconds
              from public.calls
              where organization_id = %s
                and created_at >= %s::date
                and created_at < (%s::date + interval '1 day')
            )
            select
              count(*)::int as total_calls,
              count(*) filter (where outcome = 'ANSWERED_RESOLVED')::int
                as resolved_on_first_follow_up,
              count(*) filter (where outcome = 'ESCALATED')::int as escalated_calls,
              count(*) filter (where status in ('COMPLETED', 'IN-PROGRESS'))::int
                as answered_calls,
              coalesce(avg(duration_seconds) filter (where duration_seconds is not null), 0)::float
                as average_duration_seconds
            from scoped
            """,
            (context.organization_id, period_start, period_end),
        ).fetchone()
        values = row or {
            "total_calls": 0,
            "resolved_on_first_follow_up": 0,
            "escalated_calls": 0,
            "answered_calls": 0,
            "average_duration_seconds": 0.0,
        }
        total = int(values["total_calls"])
        answered = int(values["answered_calls"])
        resolved = int(values["resolved_on_first_follow_up"])
        escalated = int(values["escalated_calls"])
        answer_rate, fcr_rate = calculate_fcr_metrics(
            total_calls=total,
            answered_calls=answered,
            resolved_calls=resolved,
        )
        report_text = (
            f"تقرير المتابعات من {period_start} إلى {period_end}: "
            f"إجمالي المكالمات {total}، نسبة الرد {answer_rate:.1%}، "
            f"نسبة الحل من أول متابعة {fcr_rate:.1%}، "
            f"المكالمات المصعدة {escalated}، ومتوسط المدة "
            f"{float(values['average_duration_seconds']):.1f} ثانية."
        )
        connection.execute(
            """
            insert into public.fcr_reports
              (organization_id, period_start, period_end, total_calls,
               resolved_on_first_follow_up, escalated_calls, report_msa)
            values (%s, %s, %s, %s, %s, %s, %s)
            on conflict (organization_id, period_start, period_end) do update set
              total_calls = excluded.total_calls,
              resolved_on_first_follow_up = excluded.resolved_on_first_follow_up,
              escalated_calls = excluded.escalated_calls,
              report_msa = excluded.report_msa,
              generated_at = now()
            """,
            (
                context.organization_id,
                period_start,
                period_end,
                total,
                resolved,
                escalated,
                report_text,
            ),
        )
    return FcrReport(
        organization_id=context.organization_id,
        period_start=period_start,
        period_end=period_end,
        total_calls=total,
        resolved_on_first_follow_up=resolved,
        escalated_calls=escalated,
        answer_rate=answer_rate,
        fcr_rate=fcr_rate,
        average_duration_seconds=float(values["average_duration_seconds"]),
        report_text=report_text,
    )
