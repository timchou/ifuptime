# Generated by Django 4.2.23 on 2025-06-27 09:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('monitoring', '0005_alter_monitor_frequency'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='user_type',
            field=models.CharField(choices=[('normal', 'Normal User'), ('pro', 'Pro User')], default='normal', help_text='Type of user, affecting monitoring limits.', max_length=10),
        ),
        migrations.AlterField(
            model_name='monitor',
            name='frequency',
            field=models.PositiveIntegerField(choices=[(300, '5 minutes'), (600, '10 minutes'), (3600, '1 hour'), (43200, '12 hours'), (86400, '24 hours')], default=300),
        ),
    ]
