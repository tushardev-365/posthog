from datetime import timedelta

from django.utils import timezone

from posthog.models.team import Team

from products.pulse.backend.models import BriefConfig
from products.pulse.backend.sources.base import EvidenceRef, EvidenceType, SourceItem, SourceItemKind
from products.signals.backend.facade.api import get_recent_reports

# Deliberately duplicates the facade's default limit: pulse owns its own prompt budget.
MAX_REPORTS = 20
TITLE_MAX_CHARS = 200
SUMMARY_MAX_CHARS = 1000


class SignalReportsSource:
    """Recent signals-inbox reports (scout and replay-vision findings) surfaced as signal items —
    pre-analyzed detections the LLM weighs as evidence when forming the narrative.

    No availability gate needed: the facade read is already scoped to inbox-visible reports (and
    returns [] without AI consent), so a team with no reports simply has nothing to gather.
    """

    name = "signal_reports"

    def gather(self, team: Team, config: BriefConfig | None, lookback_days: int) -> list[SourceItem]:
        since = timezone.now() - timedelta(days=lookback_days)
        items: list[SourceItem] = []
        for report in get_recent_reports(team.id, since=since, limit=MAX_REPORTS):
            title = report.title[:TITLE_MAX_CHARS]
            # Untrusted free text (LLM-authored report prose) is sanitized once at the
            # prompt-render boundary (_render_items).
            items.append(
                SourceItem(
                    source=self.name,
                    kind=SourceItemKind.SIGNAL,
                    title=title,
                    description=report.summary[:SUMMARY_MAX_CHARS],
                    metrics={"weight": report.total_weight, "signal_count": report.signal_count},
                    evidence=[EvidenceRef(type=EvidenceType.SIGNAL_REPORT, ref=str(report.id), label=title)],
                    fingerprint_hint=f"signal_report:{report.id}",
                )
            )
        return items
