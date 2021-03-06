# -*- coding: utf-8 -*-
# Generated by Django 1.11.11 on 2018-04-03 10:29
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('indicator', '0007_auto_20180305_1813'),
    ]

    operations = [
        migrations.AddField(
            model_name='disaggregation',
            name='external_source',
            field=models.TextField(blank=True, choices=[('HPC', 'HPC'), ('OPS', 'OPS')], null=True),
        ),
        migrations.AddField(
            model_name='disaggregationvalue',
            name='external_source',
            field=models.TextField(blank=True, choices=[('HPC', 'HPC'), ('OPS', 'OPS')], null=True),
        ),
        migrations.AlterUniqueTogether(
            name='disaggregationvalue',
            unique_together=set([('external_id', 'external_source')]),
        ),
    ]
