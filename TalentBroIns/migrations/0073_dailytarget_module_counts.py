import django.core.validators
from django.db import migrations, models

# The eight self-training module count columns, in the order the /daily-targets
# screen lists them. Spelled out rather than generated so the migration is a
# frozen record of the schema it produced.
_COUNT_FIELDS = [
    ('communication_count', 'Communication Skills'),
    ('group_discussion_count', 'Group Discussion'),
    ('aplr_count', 'Aptitude & Logical Reasoning'),
    ('basic_math_count', 'Mathematics'),
    ('english_count', 'English Trainer'),
    ('situational_count', 'Situational Problem Solving Skills (Management)'),
    ('technical_count', 'Problem Solving Skills (Technical)'),
    ('dsa_count', 'DSA (Data Structures & Algorithms)'),
]

# A tick in the old "modules" list becomes a target of one item, which is the
# closest the new count columns can say about "this module is part of today".
_TICKED_TO_ONE = {
    'communication': 'communication_count',
    'group_discussion': 'group_discussion_count',
    'aplr': 'aplr_count',
    'basic_math': 'basic_math_count',
    'english': 'english_count',
    'situational': 'situational_count',
    'technical': 'technical_count',
    'dsa': 'dsa_count',
}


def ticked_modules_to_counts(apps, schema_editor):
    """Carry ticked modules over as a count of one.

    A key the platform no longer offers has nowhere to go, so it is dropped
    rather than guessed at.
    """
    daily_target = apps.get_model('TalentBroIns', 'DailyTarget')
    for target in daily_target.objects.all().iterator():
        stored = target.modules if isinstance(target.modules, list) else []
        for key in stored:
            field = _TICKED_TO_ONE.get(str(key))
            if field:
                setattr(target, field, 1)
        target.save(update_fields=list(_TICKED_TO_ONE.values()))


def counts_to_ticked_modules(apps, schema_editor):
    """Reverse step: any module with a count becomes a tick again."""
    daily_target = apps.get_model('TalentBroIns', 'DailyTarget')
    for target in daily_target.objects.all().iterator():
        modules = [
            key for key, field in _TICKED_TO_ONE.items()
            if getattr(target, field)
        ]
        target.modules = modules
        target.save(update_fields=['modules'])


class Migration(migrations.Migration):

    dependencies = [
        ('TalentBroIns', '0072_daily_target'),
    ]

    operations = [
        # The underscore in the class name was a typo that had reached the table
        # name, so rename the model (and with it the table) rather than dropping
        # the table and every stored candidate's plan with it.
        migrations.RenameModel(
            old_name='Daily_Target',
            new_name='DailyTarget',
        ),
        # A boolean "is a mock interview on the menu" became a count, so the
        # column is renamed first (keeping the stored 0/1, which reads as the
        # count) and then re-typed.
        migrations.RenameField(
            model_name='dailytarget',
            old_name='mock_interview',
            new_name='mock_count',
        ),
        migrations.AlterField(
            model_name='dailytarget',
            name='mock_count',
            field=models.PositiveIntegerField(
                default=0,
                help_text='How many mock interviews are targeted for the day.',
                validators=[
                    django.core.validators.MinValueValidator(0),
                    django.core.validators.MaxValueValidator(20),
                ],
            ),
        ),
        # The minutes were always a target for the day, not time already spent,
        # so the name now says so.
        migrations.RenameField(
            model_name='dailytarget',
            old_name='time_spent',
            new_name='time_target',
        ),
        # Each module gets its own count instead of a shared JSON tick list, so
        # the setter can commit to a number of items per module.
        *[
            migrations.AddField(
                model_name='dailytarget',
                name=name,
                field=models.PositiveIntegerField(
                    default=0,
                    help_text=f'How many {label} items are targeted for the day.',
                    validators=[
                        django.core.validators.MinValueValidator(0),
                        django.core.validators.MaxValueValidator(20),
                    ],
                ),
            )
            for name, label in _COUNT_FIELDS
        ],
        migrations.RunPython(ticked_modules_to_counts, counts_to_ticked_modules),
        migrations.RemoveField(
            model_name='dailytarget',
            name='modules',
        ),
    ]
