from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('TalentBroIns', '0064_alter_candidateprofile_readiness_department_total_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='candidateprofile',
            name='time_spent',
            field=models.PositiveIntegerField(default=0, help_text='Total time spent on the platform, in minutes (cumulative across sessions).'),
        ),
    ]