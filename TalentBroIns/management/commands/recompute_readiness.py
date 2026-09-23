import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from TalentBroIns.models import CandidateProfile
from TalentBroIns.views import _refresh_readiness_college


class Command(BaseCommand):
    help = 'Recompute and persist readiness score / AIR / department rank for every candidate.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--college',
            type=int,
            default=None,
            help='Only recompute for this college (institution) id. Defaults to all colleges.',
        )

    def handle(self, *args, **options):
        college_id = options.get('college')
        colleges = list(
            CandidateProfile.objects
            .filter(college_id__isnull=False)
            .order_by('college_id')
            .values_list('college_id', flat=True)
            .distinct()
        )
        if college_id is not None:
            colleges = [c for c in colleges if c == college_id]

        if not colleges:
            self.stdout.write(self.style.WARNING('No candidates with a college assigned.'))
            return

        started = time.time()
        total = sum(
            CandidateProfile.objects.filter(college_id=cid).count()
            for cid in colleges
        )
        updated = 0
        for cid in colleges:
            _, overall, department, totals = _refresh_readiness_college(college_id=cid)
            updated += len(overall)
            self.stdout.write(
                f'College {cid}: {len(overall)} ranked of '
                f'{totals["overall_total"]} total '
                f'({len(department)} departments)'
            )

        elapsed = time.time() - started
        self.stdout.write(self.style.SUCCESS(
            f'Done: recomputed {total} candidates across {len(colleges)} colleges, '
            f'{updated} ranked, persisted to CandidateProfile '
            f'({elapsed:.2f}s) at {timezone.now().isoformat()}.'
        ))