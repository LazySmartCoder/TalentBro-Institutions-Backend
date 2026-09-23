from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('TalentBroIns', '0057_remove_candidateprofile_college_email'),
    ]

    operations = [
        migrations.DeleteModel(
            name='GroupDiscussionTraining',
        ),
    ]
