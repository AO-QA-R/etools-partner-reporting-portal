# -*- coding: utf-8 -*-
# Generated by Django 1.11.11 on 2018-04-27 20:59
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('indicator', '0019_merge_20180427_2053'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='reportable',
            name='created_by',
        ),
    ]
