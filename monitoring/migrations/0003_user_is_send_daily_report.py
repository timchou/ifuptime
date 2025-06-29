# Generated by Django 4.2.23 on 2025-06-27 05:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('monitoring', '0002_node_monitorlog_node_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='is_send_daily_report',
            field=models.BooleanField(default=False, help_text='Whether to send daily monitoring reports to this user.'),
        ),
    ]
