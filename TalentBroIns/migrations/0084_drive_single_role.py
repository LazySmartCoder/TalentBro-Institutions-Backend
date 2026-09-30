from django.db import migrations, models


def roles_to_single_role(apps, schema_editor):
    """Collapse each drive's role list down to its first title.

    A drive now holds exactly one role, so the old JSON list has to become a
    string. The first entry wins: a company hiring for two roles schedules two
    drives, and dropping the extras is better than losing the whole drive. The
    per-role vacancy counts are folded into total_vacancies when the drive never
    recorded one, so the openings figure on every screen survives the reshape.
    """
    Drive = apps.get_model('TalentBroIns', 'Drive')
    for drive in Drive.objects.all().iterator():
        raw = drive.roles or []
        titles = []
        vacancies = 0
        for entry in raw:
            if isinstance(entry, dict):
                title = str(entry.get('title') or '').strip()
                if title:
                    titles.append(title)
                vacancies += int(entry.get('vacancies') or 0)
            elif str(entry).strip():
                titles.append(str(entry).strip())
        if not titles:
            continue
        drive.role = titles[0][:255]
        if drive.total_vacancies is None and vacancies:
            drive.total_vacancies = vacancies
        drive.save(update_fields=['role', 'total_vacancies'])


def single_role_to_roles(apps, schema_editor):
    """Put the single role back into a one-entry list on the way down."""
    Drive = apps.get_model('TalentBroIns', 'Drive')
    for drive in Drive.objects.all().iterator():
        drive.roles = ([{'title': drive.role, 'description': '', 'vacancies': 0}]
                       if drive.role else [])
        drive.save(update_fields=['roles'])


class Migration(migrations.Migration):

    dependencies = [
        ('TalentBroIns', '0083_alter_candidateprofile_placement_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='drive',
            name='role',
            field=models.CharField(
                blank=True, default='',
                help_text='The role this drive is hiring for, e.g. Software Engineer.',
                max_length=255,
            ),
        ),
        migrations.RunPython(roles_to_single_role, single_role_to_roles),
        migrations.RemoveField(
            model_name='drive',
            name='roles',
        ),
        migrations.AlterField(
            model_name='drive',
            name='total_vacancies',
            field=models.PositiveIntegerField(
                blank=True, help_text='Openings for this drive.', null=True
            ),
        ),
    ]
