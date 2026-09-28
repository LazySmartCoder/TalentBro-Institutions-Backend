"""One-shot / repeatable script: copy the ENTIRE SQLite database into the
production PostgreSQL (Supabase) database, keeping db.sqlite3 untouched.

Run from the Backend directory:

    py migrate_to_production.py

Flow:
  1. Apply all Django migrations to the empty production Postgres DB
     (fresh schema + regenerated contenttypes/permissions).
  2. dumpdata the whole SQLite DB using natural keys.
  3. loaddata that fixture into Postgres.
  4. Reset every Postgres sequence to MAX(id) so new inserts can't collide.
  5. Print a per-model row-count comparison (SQLite vs Postgres).

The Postgres DB must be EMPTY for a clean load. Re-running against a
non-empty DB will fail with duplicate-key errors; that's intentional.
"""

import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
FIXTURE = os.path.join(BASE, 'db_dump.json')
EXCLUDED = ['contenttypes', 'auth.Permission']


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'TalentBro.migrate_settings')
    sys.path.insert(0, BASE)
    import django
    django.setup()

    from django.apps import apps
    from django.core.management import call_command
    from django.db import connection

    print('[1/5] Applying migrations to production PostgreSQL ...')
    call_command('migrate', database='default', interactive=False, verbosity=1)

    print('[2/5] Dumping SQLite -> %s' % FIXTURE)
    with open(FIXTURE, 'w', encoding='utf-8') as out:
        old_stdout = sys.stdout
        sys.stdout = out
        try:
            call_command(
                'dumpdata',
                database='sqlite',
                natural_primary=True,
                natural_foreign=True,
                exclude=EXCLUDED,
                verbosity=0,
            )
        finally:
            sys.stdout = old_stdout

    print('[3/5] Loading dump into production PostgreSQL ...')
    call_command('loaddata', FIXTURE, database='default', verbosity=1)

    print('[4/5] Resetting PostgreSQL sequences ...')
    app_labels = [cfg.label for cfg in apps.get_app_configs()]
    reset_sql = call_command('sqlsequencereset', *app_labels)
    with connection.cursor() as cursor:
        for statement in reset_sql.strip().split(';'):
            statement = statement.strip()
            if statement:
                cursor.execute(statement)

    print('[5/5] Row-count comparison (model | sqlite -> postgres):')
    for model in apps.get_models():
        label = '%s.%s' % (model._meta.app_label, model._meta.model_name)
        s = model.objects.using('sqlite').count()
        p = model.objects.using('default').count()
        marker = '' if s == p else '   <-- MISMATCH'
        print('  %-55s %8d -> %8d%s' % (label, s, p, marker))

    print('Done. SQLite db.sqlite3 left untouched; fixture kept at db_dump.json.')


if __name__ == '__main__':
    main()