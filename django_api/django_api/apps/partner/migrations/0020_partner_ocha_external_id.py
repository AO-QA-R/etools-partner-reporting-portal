# -*- coding: utf-8 -*-
# Generated by Django 1.11.11 on 2018-05-11 11:26
from __future__ import unicode_literals

import core.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('partner', '0019_auto_20180427_2059'),
    ]

    operations = [
        migrations.AddField(
            model_name='partner',
            name='ocha_external_id',
            field=core.fields.UniqueNullCharField(blank=True, max_length=128, null=True, unique=True),
        ),
    ]
