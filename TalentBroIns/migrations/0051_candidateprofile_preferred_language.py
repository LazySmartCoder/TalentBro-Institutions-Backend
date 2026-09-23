from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('TalentBroIns', '0050_english_writing_metrics'),
    ]

    operations = [
        migrations.AddField(
            model_name='candidateprofile',
            name='preferred_language',
            field=models.CharField(blank=True, choices=[('english', 'English'), ('hindi', 'Hindi'), ('bengali', 'Bengali'), ('tamil', 'Tamil'), ('telugu', 'Telugu'), ('marathi', 'Marathi'), ('kannada', 'Kannada'), ('gujarati', 'Gujarati'), ('malayalam', 'Malayalam'), ('punjabi', 'Punjabi'), ('odia', 'Odia'), ('assamese', 'Assamese'), ('urdu', 'Urdu')], default='', help_text="The candidate's preferred language (e.g., English, Hindi, Bengali).", max_length=30),
        ),
    ]
