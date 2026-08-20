"""Arabic reporting-agent facade over deterministic FCR aggregates."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date

from outbound_ai.db.connection import TenantContext
from outbound_ai.reports.service import FcrReport, generate_fcr_report


def generate_reporting_article(
    *,
    context: TenantContext,
    period_start: date,
    period_end: date,
) -> dict:
    """Return stable report data suitable for a dashboard or quality article."""

    report: FcrReport = generate_fcr_report(
        context=context,
        period_start=period_start,
        period_end=period_end,
    )
    return {
        **asdict(report),
        "organization_id": str(report.organization_id),
        "period_start": report.period_start.isoformat(),
        "period_end": report.period_end.isoformat(),
        "headline": "تقرير جودة المتابعات وأول حل للمشكلة",
        "recommendations": [
            "راجع المكالمات غير المجابة وجدول إعادة الاتصال المناسب.",
            "راجع أسباب التصعيد لتحسين الإجراء السابق للمكالمة.",
            "قارن التقرير بعينة تدقيق بشرية قبل استخدامه كمؤشر رسمي.",
        ],
    }
