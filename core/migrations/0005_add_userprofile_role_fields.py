# Generated manually to add role fields to UserProfile

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_alter_school_email_school_unique_school_name_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='role',
            field=models.CharField(
                choices=[
                    ('super_admin', 'Super Admin'),
                    ('school_admin', 'School Admin'),
                    ('teacher', 'Teacher'),
                    ('accountant', 'Accountant'),
                    ('parent', 'Parent'),
                    ('student', 'Student'),
                ],
                default='teacher',
                max_length=20
            ),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='is_active',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, null=True, blank=True),
        ),
    ]

