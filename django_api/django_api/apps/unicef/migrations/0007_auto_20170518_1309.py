# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-05-18 13:09
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('indicator', '0002_auto_20170517_1128'),
        ('unicef', '0006_auto_20170517_1128'),
    ]

    operations = [
        migrations.AddField(
            model_name='programmedocument',
            name='reportable',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, to='indicator.Reportable'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='programmedocument',
            name='administrative_level',
            field=models.CharField(choices=[('Cou', 'Country level'), ('Reg', 'Region level'), ('Cit', 'City level')], default='Cou', max_length=3, verbose_name='Locations - administrative level'),
        ),
    ]
