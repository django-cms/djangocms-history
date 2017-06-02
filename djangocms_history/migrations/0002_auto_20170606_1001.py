# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djangocms_history', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='placeholderaction',
            name='language',
            field=models.CharField(max_length=15, choices=settings.LANGUAGES),
        ),
        migrations.AlterField(
            model_name='placeholderoperation',
            name='language',
            field=models.CharField(max_length=15, choices=settings.LANGUAGES),
        ),
    ]
