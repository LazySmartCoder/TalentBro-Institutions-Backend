from django.db import migrations


class Migration(migrations.Migration):
    """Drop the hand-typed company list from Institution.

    The field was a comma-separated names blob that nothing wrote to except the
    admin, so it drifted from reality: a company could be on it after its
    account was deleted, and absent after a drive was scheduled. Both read paths
    that used it (the student chat context and /api/institutions/companies/) now
    read the Company rows instead, which is the record that actually carries the
    drives, rounds and eligibility behind a name.
    """

    dependencies = [
        ('TalentBroIns', '0089_classroomldsession'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='institution',
            name='companies',
        ),
    ]
