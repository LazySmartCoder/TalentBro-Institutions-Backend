import TalentBroIns.models
import django.core.validators
import django.db.models.deletion
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('TalentBroIns', '0002_userprofile'),
    ]

    operations = [
        migrations.AddField(
            model_name='institution',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='institution',
            name='institution_type',
            field=models.CharField(choices=TalentBroIns.models.INSTITUTION_TYPE_CHOICES, default='', max_length=30),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='institution',
            name='website',
            field=models.URLField(blank=True, default=''),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='institution',
            name='email_domain',
            field=models.CharField(default='', max_length=255),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='institution',
            name='address',
            field=models.TextField(default=''),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='institution',
            name='city',
            field=models.CharField(default='', max_length=100),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='institution',
            name='state',
            field=models.CharField(default='', max_length=100),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='institution',
            name='pin_code',
            field=models.CharField(default='', max_length=6, validators=[django.core.validators.RegexValidator(regex='^[1-9][0-9]{5}$', message='Enter a valid 6-digit PIN Code.')]),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='institution',
            name='logo',
            field=models.ImageField(blank=True, null=True, upload_to='institution_logos/'),
        ),
        migrations.AddField(
            model_name='institution',
            name='placement_department_name',
            field=models.CharField(default='', max_length=255),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='institution',
            name='placement_office_email',
            field=models.EmailField(default='', max_length=254),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='institution',
            name='approximate_student_strength',
            field=models.PositiveIntegerField(default=0),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='institution',
            name='courses_offered',
            field=models.JSONField(default=list),
        ),
        migrations.RemoveField(
            model_name='userprofile',
            name='institution_type',
        ),
        migrations.RemoveField(
            model_name='userprofile',
            name='institution_website',
        ),
        migrations.RemoveField(
            model_name='userprofile',
            name='institution_email_domain',
        ),
        migrations.RemoveField(
            model_name='userprofile',
            name='institution_address',
        ),
        migrations.RemoveField(
            model_name='userprofile',
            name='city',
        ),
        migrations.RemoveField(
            model_name='userprofile',
            name='state',
        ),
        migrations.RemoveField(
            model_name='userprofile',
            name='pin_code',
        ),
        migrations.RemoveField(
            model_name='userprofile',
            name='institution_logo',
        ),
        migrations.RemoveField(
            model_name='userprofile',
            name='placement_department_name',
        ),
        migrations.RemoveField(
            model_name='userprofile',
            name='placement_office_email',
        ),
        migrations.RemoveField(
            model_name='userprofile',
            name='approximate_student_strength',
        ),
        migrations.RemoveField(
            model_name='userprofile',
            name='courses_offered',
        ),
        migrations.RemoveField(
            model_name='userprofile',
            name='institution_name',
        ),
        migrations.AlterModelOptions(
            name='institution',
            options={'ordering': ['name']},
        ),
        migrations.AlterModelOptions(
            name='userprofile',
            options={'ordering': ['full_name']},
        ),
        migrations.AddField(
            model_name='userprofile',
            name='institution',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, related_name='profiles', to='TalentBroIns.institution'),
            preserve_default=False,
        ),
    ]
