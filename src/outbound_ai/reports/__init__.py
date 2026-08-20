"""Organization-scoped FCR reports and reporting-agent helpers."""

from outbound_ai.reports.agent import generate_reporting_article
from outbound_ai.reports.service import FcrReport, generate_fcr_report

__all__ = ["FcrReport", "generate_fcr_report", "generate_reporting_article"]
