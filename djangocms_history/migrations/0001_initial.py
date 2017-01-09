# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('cms', '0016_auto_20160608_1535'),
        ('sites', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PlaceholderAction',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('action', models.CharField(max_length=30, choices=[('add_plugin', 'Add plugin'), ('change_plugin', 'Change plugin'), ('delete_plugin', 'Delete plugin'), ('move_plugin', 'Move plugin'), ('move_out_plugin', 'Move out plugin'), ('move_in_plugin', 'Move in plugin'), ('move_plugin_out_to_clipboard', 'Move out to clipboard'), ('move_plugin_in_to_clipboard', 'Move in to clipboard'), ('add_plugins_from_placeholder', 'Add plugins from placeholder'), ('paste_plugin', 'Paste plugin'), ('paste_placeholder', 'Paste placeholder'), ('clear_placeholder', 'Clear placeholder')])),
                ('pre_action_data', models.TextField(blank=True)),
                ('post_action_data', models.TextField(blank=True)),
                ('language', models.CharField(max_length=5, choices=settings.LANGUAGES)),
                ('order', models.PositiveIntegerField(default=1)),
            ],
            options={
                'ordering': ['order'],
            },
        ),
        migrations.CreateModel(
            name='PlaceholderOperation',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('operation_type', models.CharField(max_length=30, choices=[('add_plugin', 'Add plugin'), ('change_plugin', 'Change plugin'), ('delete_plugin', 'Delete plugin'), ('move_plugin', 'Move plugin'), ('cut_plugin', 'Cut plugin'), ('paste_plugin', 'Paste plugin'), ('paste_placeholder', 'Paste placeholder'), ('add_plugins_from_placeholder', 'Add plugins from placeholder'), ('clear_placeholder', 'Clear placeholder')])),
                ('token', models.CharField(max_length=120, db_index=True)),
                ('origin', models.CharField(max_length=255, db_index=True)),
                ('language', models.CharField(max_length=5, choices=settings.LANGUAGES)),
                ('user_session_key', models.CharField(max_length=120, db_index=True)),
                ('date_created', models.DateTimeField(auto_now_add=True, verbose_name='date created', db_index=True)),
                ('is_applied', models.BooleanField(default=False)),
                ('is_archived', models.BooleanField(default=False)),
                ('site', models.ForeignKey(to='sites.Site')),
                ('user', models.ForeignKey(verbose_name='user', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-date_created'],
                'get_latest_by': 'date_created',
            },
        ),
        migrations.AddField(
            model_name='placeholderaction',
            name='operation',
            field=models.ForeignKey(related_name='actions', to='djangocms_history.PlaceholderOperation'),
        ),
        migrations.AddField(
            model_name='placeholderaction',
            name='placeholder',
            field=models.ForeignKey(to='cms.Placeholder'),
        ),
        migrations.AlterUniqueTogether(
            name='placeholderaction',
            unique_together=set([('operation', 'order')]),
        ),
    ]
