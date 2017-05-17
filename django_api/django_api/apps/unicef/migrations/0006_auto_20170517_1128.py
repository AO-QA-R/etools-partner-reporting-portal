# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-05-17 11:28
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('unicef', '0005_programmedocument_frequency'),
    ]

    operations = [
        migrations.AlterField(
            model_name='programmedocument',
            name='end_date',
            field=models.DateField(verbose_name='Due Date'),
        ),
        migrations.AlterField(
            model_name='programmedocument',
            name='frequency',
            field=models.CharField(choices=[('Wee', 'Weekly'), ('Mon', 'Monthly'), ('Qua', 'Quarterly')], default='Mon', max_length=3, verbose_name='Frequency of reporting'),
        ),
        migrations.AlterField(
            model_name='programmedocument',
            name='start_date',
            field=models.DateField(verbose_name='Start Programme Date'),
        ),
    ]
