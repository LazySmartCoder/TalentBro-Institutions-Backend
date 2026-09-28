"""Django settings override used ONLY by migrate_to_production.py.

Exposes two database aliases at once:
  * ``default``  -> the production PostgreSQL (Supabase) database
  * ``sqlite``   -> the existing local SQLite database (kept untouched)

Everything else is inherited from ``TalentBro.settings``.
"""

from .settings import *  # noqa: F401,F403
from .settings import BASE_DIR, DATABASES

_prod_db = dict(DATABASES)['default']

DATABASES = {
    'default': _prod_db,
    'sqlite': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': str(BASE_DIR / 'db.sqlite3'),
    },
}