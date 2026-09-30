"""Print every field the configured Apify actor returns for a LinkedIn profile.

Usage, from Backend/:

    python list_linkedin_fields.py                      # default profile
    python list_linkedin_fields.py <linkedin-url>       # a specific profile
    python list_linkedin_fields.py <linkedin-url> <actor-id>

Free tier only: this uses whatever actor is configured in APIFY_LINKEDIN_ACTOR,
which is a free actor. Each run costs a fraction of the $5/month allowance, so
use it sparingly.
"""

import json
import os
import sys

import requests
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
load_dotenv('.env')

DEFAULT_ACTOR = 'calm_builder~linkedin-profile-scraper'
DEFAULT_PROFILE = 'https://www.linkedin.com/in/williamhgates'


def fetch(actor, profile):
    response = requests.post(
        f'https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items',
        params={'token': os.environ['APIFY_TOKEN']},
        json={'profiles': [profile]},
        timeout=180,
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        raise SystemExit(f'{actor} returned no usable item: {data!r:.200}')
    return data[0]


def main():
    profile = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PROFILE
    actor = sys.argv[2] if len(sys.argv) > 2 else os.environ.get(
        'APIFY_LINKEDIN_ACTOR', DEFAULT_ACTOR
    )

    item = fetch(actor, profile)

    scalars, lists_, dicts = [], [], []
    for key in sorted(item):
        value = item[key]
        if isinstance(value, list):
            lists_.append((key, value))
        elif isinstance(value, dict):
            dicts.append((key, value))
        else:
            scalars.append((key, value))

    print('=' * 78)
    print(f'actor  : {actor}')
    print(f'profile: {profile}')
    print(f'fields : {len(item)} top-level keys')
    print('=' * 78)

    print(f'\n--- scalar fields ({len(scalars)}) ---')
    for key, value in scalars:
        print(f'  {key:26} {str(value)[:60]!r}')

    print(f'\n--- list fields ({len(lists_)}) ---')
    for key, value in lists_:
        print(f'  {key:26} {len(value)} entries')
        if value:
            subkeys = sorted(value[0]) if isinstance(value[0], dict) else []
            print(f'  {"":26}   entry keys: {subkeys}')

    print(f'\n--- object fields ({len(dicts)}) ---')
    for key, value in dicts:
        print(f'  {key:26} {sorted(value)}')

    # Count how much detail the experience and education entries actually carry,
    # since a logged-out actor returns the section but strips most of it.
    print('\n--- detail check: are entries usable for a resume? ---')
    for section in ('experience', 'experiences', 'education', 'educations'):
        for key, value in item.items():
            if key != section or not isinstance(value, list) or not value:
                continue
            first = value[0]
            if not isinstance(first, dict):
                continue
            for field in ('title', 'company', 'companyName', 'school',
                          'degree', 'dateRange', 'startDate', 'endDate', 'location'):
                print(f'  {section}.{field:14} '
                      f'{first[field]!r:.60}' if field in first
                      else f'  {section}.{field:14} ABSENT')


if __name__ == '__main__':
    main()
