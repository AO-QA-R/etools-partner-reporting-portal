# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-05-24 21:39
from __future__ import unicode_literals

import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import model_utils.fields


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_auto_20170515_1017'),
        ('indicator', '0003_remove_indicatorreport_programme_document'),
    ]

    operations = [
        migrations.CreateModel(
            name='IndicatorLocationData',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('disaggregation', django.contrib.postgres.fields.jsonb.JSONField(default=dict)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.RenameField(
            model_name='indicatorreport',
            old_name='time_period',
            new_name='time_period_start',
        ),
        migrations.RemoveField(
            model_name='indicatorreport',
            name='disaggregation',
        ),
        migrations.RemoveField(
            model_name='indicatorreport',
            name='is_disaggregated_report',
        ),
        migrations.AddField(
            model_name='indicatorreport',
            name='time_period_end',
            field=models.DateField(default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='indicatorlocationdata',
            name='indicator_report',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='indicator_location_data', to='indicator.IndicatorReport'),
        ),
        migrations.AddField(
            model_name='indicatorlocationdata',
            name='location',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='indicator_location_data', to='core.Location'),
        ),
    ]
