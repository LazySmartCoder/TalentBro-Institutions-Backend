import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


def delete_incomplete_candidates(apps, schema_editor):
    """Remove any existing CandidateProfile rows that would violate the new
    required-field constraints (all rows are incomplete dev/test data)."""
    CandidateProfile = apps.get_model('TalentBroIns', 'CandidateProfile')
    CandidateProfile.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('TalentBroIns', '0022_clientprofile_access'),
    ]

    operations = [
        migrations.RunPython(
            delete_incomplete_candidates,
            migrations.RunPython.noop,
        ),
        migrations.RemoveField(
            model_name='candidateprofile',
            name='batch_year',
        ),
        migrations.RemoveField(
            model_name='candidateprofile',
            name='current_year',
        ),
        migrations.RemoveField(
            model_name='candidateprofile',
            name='percentage',
        ),
        migrations.RemoveField(
            model_name='candidateprofile',
            name='specialization',
        ),
        migrations.AlterField(
            model_name='candidateprofile',
            name='college',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='candidate_profiles', to='TalentBroIns.institution'),
        ),
        migrations.AlterField(
            model_name='candidateprofile',
            name='date_of_birth',
            field=models.DateField(),
        ),
        migrations.AlterField(
            model_name='candidateprofile',
            name='department',
            field=models.CharField(max_length=120),
        ),
        migrations.AlterField(
            model_name='candidateprofile',
            name='full_name',
            field=models.CharField(max_length=255),
        ),
        migrations.AlterField(
            model_name='candidateprofile',
            name='gender',
            field=models.CharField(choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other'), ('prefer_not_to_say', 'Prefer Not to Say')], default='', max_length=20),
        ),
        migrations.AlterField(
            model_name='candidateprofile',
            name='linkedin_url',
            field=models.URLField(),
        ),
        migrations.AlterField(
            model_name='candidateprofile',
            name='mobile_number',
            field=models.CharField(max_length=16, validators=[django.core.validators.RegexValidator(message='Enter a valid mobile number (10-15 digits).', regex='^\\+?[0-9]{10,15}$')]),
        ),
        migrations.AlterField(
            model_name='candidateprofile',
            name='program',
            field=models.CharField(choices=[('B.Tech', 'B.Tech'), ('B.E.', 'B.E.'), ('BCA', 'BCA'), ('BBA', 'BBA'), ('B.Com', 'B.Com'), ('B.Sc.', 'B.Sc.'), ('BA', 'BA'), ('BMS', 'BMS'), ('BBM', 'BBM'), ('B.Des', 'B.Des'), ('B.Arch', 'B.Arch'), ('B.Pharm', 'B.Pharm'), ('MBBS', 'MBBS'), ('BDS', 'BDS'), ('BAMS', 'BAMS'), ('BHMS', 'BHMS'), ('BPT', 'BPT'), ('B.Sc. Nursing', 'B.Sc. Nursing'), ('B.Ed', 'B.Ed'), ('LLB', 'LLB'), ('BA LLB', 'BA LLB'), ('BBA LLB', 'BBA LLB'), ('BJMC', 'BJMC'), ('BHM', 'BHM'), ('BFA', 'BFA'), ('B.Voc', 'B.Voc'), ('M.Tech', 'M.Tech'), ('M.E.', 'M.E.'), ('MCA', 'MCA'), ('MBA', 'MBA'), ('PGDM', 'PGDM'), ('M.Com', 'M.Com'), ('M.Sc.', 'M.Sc.'), ('MA', 'MA'), ('M.Des', 'M.Des'), ('M.Arch', 'M.Arch'), ('M.Pharm', 'M.Pharm'), ('M.Ed', 'M.Ed'), ('LLM', 'LLM'), ('MPT', 'MPT'), ('Diploma', 'Diploma'), ('ITI', 'ITI'), ('PG Diploma', 'PG Diploma'), ('Ph.D.', 'Ph.D.'), ('Other', 'Other')], default='', max_length=120),
        ),
        migrations.AlterField(
            model_name='candidateprofile',
            name='resume_url',
            field=models.URLField(),
        ),
        migrations.AddField(
            model_name='candidateprofile',
            name='cgpa',
            field=models.DecimalField(decimal_places=2, max_digits=4),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='candidateprofile',
            name='end_year',
            field=models.PositiveIntegerField(),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='candidateprofile',
            name='start_year',
            field=models.PositiveIntegerField(),
            preserve_default=False,
        ),
    ]
