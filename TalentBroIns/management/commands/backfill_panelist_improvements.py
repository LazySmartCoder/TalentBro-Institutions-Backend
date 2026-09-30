from django.core.management.base import BaseCommand

from TalentBroIns.models import (
    MOCK_INTERVIEW_ANALYSIS_PANELISTS,
    MOCK_INTERVIEW_STATUS_COMPLETED,
    MockInterview,
)
from TalentBroIns.views import _get_interview_analysis, _mock_analysis_generate


class Command(BaseCommand):
    help = (
        'Regenerate the analysis for completed mock interviews so every panelist '
        'who sat on them has an improvement area. Interviews already carrying '
        'remarks are skipped unless --force is passed.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Only touch the most recent N interviews. Defaults to all.',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Regenerate even for interviews that already have panelist remarks.',
        )

    def handle(self, *args, **options):
        limit = options.get('limit') or 0
        force = bool(options.get('force'))

        interviews = MockInterview.objects.filter(
            status=MOCK_INTERVIEW_STATUS_COMPLETED,
        ).order_by('-updated_at')
        if limit:
            interviews = interviews[:limit]

        pending = []
        for interview in interviews:
            if force:
                pending.append(interview)
                continue
            analysis = _get_interview_analysis(interview)
            if analysis is None:
                continue
            if any(getattr(analysis, pid, '') for pid, _label in MOCK_INTERVIEW_ANALYSIS_PANELISTS):
                continue
            pending.append(interview)

        if not pending:
            self.stdout.write(self.style.WARNING(
                'Nothing to do - every completed mock interview already has panelist remarks.'
            ))
            return

        updated = 0
        for interview in pending:
            analysis = _mock_analysis_generate(interview)
            if analysis is None:
                self.stdout.write(self.style.WARNING(
                    f'{interview.pk}: analysis could not be regenerated, skipped.'
                ))
                continue
            remarks = [
                f'{pid}={getattr(analysis, pid, "")!r}'
                for pid, _label in MOCK_INTERVIEW_ANALYSIS_PANELISTS
                if getattr(analysis, pid, '')
            ]
            if not remarks:
                self.stdout.write(self.style.WARNING(
                    f'{interview.pk}: regenerated, but no panelist wrote an improvement area.'
                ))
            updated += 1

        self.stdout.write(self.style.SUCCESS(
            f'Done: regenerated {updated} of {len(pending)} mock interview analyses.'
        ))
