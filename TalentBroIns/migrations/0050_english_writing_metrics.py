from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('TalentBroIns', '0049_company_tier'),
    ]

    operations = [
        # Voice-based delivery metrics no longer apply — the English trainer is
        # now a typing/writing practice, so these columns are repurposed for
        # corporate-writing skills instead.
        migrations.RenameField(
            model_name='englishtraining',
            old_name='fluency',
            new_name='structure',
        ),
        migrations.RenameField(
            model_name='englishtraining',
            old_name='pronunciation',
            new_name='spelling',
        ),
        migrations.RenameField(
            model_name='englishtraining',
            old_name='confidence',
            new_name='conciseness',
        ),
        migrations.RenameField(
            model_name='englishtraining',
            old_name='intonation',
            new_name='task_focus',
        ),
        migrations.RenameField(
            model_name='englishtraining',
            old_name='speaking_score',
            new_name='writing_score',
        ),
        migrations.AlterField(
            model_name='englishtraining',
            name='clarity',
            field=models.PositiveSmallIntegerField(default=0, help_text='Clarity of the message score (0–100).'),
        ),
        migrations.AlterField(
            model_name='englishtraining',
            name='structure',
            field=models.PositiveSmallIntegerField(default=0, help_text='Structure and organisation score (0–100).'),
        ),
        migrations.AlterField(
            model_name='englishtraining',
            name='grammar',
            field=models.PositiveSmallIntegerField(default=0, help_text='Grammar score (0–100).'),
        ),
        migrations.AlterField(
            model_name='englishtraining',
            name='vocabulary',
            field=models.PositiveSmallIntegerField(default=0, help_text='Vocabulary and word choice score (0–100).'),
        ),
        migrations.AlterField(
            model_name='englishtraining',
            name='spelling',
            field=models.PositiveSmallIntegerField(default=0, help_text='Spelling and punctuation score (0–100).'),
        ),
        migrations.AlterField(
            model_name='englishtraining',
            name='conciseness',
            field=models.PositiveSmallIntegerField(default=0, help_text='Conciseness score (0–100).'),
        ),
        migrations.AlterField(
            model_name='englishtraining',
            name='task_focus',
            field=models.PositiveSmallIntegerField(default=0, help_text='Task focus and format score (0–100).'),
        ),
        migrations.AlterField(
            model_name='englishtraining',
            name='professional_tone',
            field=models.PositiveSmallIntegerField(default=0, help_text='Professional tone score (0–100).'),
        ),
        migrations.AlterField(
            model_name='englishtraining',
            name='writing_score',
            field=models.PositiveSmallIntegerField(default=0, help_text='Overall English writing score (0–100).'),
        ),
    ]
