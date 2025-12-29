# Migration to add SchoolClass to migration state
# The table already exists, so this will be fake-applied

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_alter_userprofile_created_at_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='SchoolClass',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('class_teacher', models.CharField(blank=True, max_length=100, null=True)),
                ('description', models.TextField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('grade', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='school_classes', to='core.grade')),
                ('school', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='school_classes', to='core.school')),
            ],
            options={
                'verbose_name': 'Class',
                'verbose_name_plural': 'Classes',
                'unique_together': {('school', 'grade', 'name')},
            },
        ),
    ]

