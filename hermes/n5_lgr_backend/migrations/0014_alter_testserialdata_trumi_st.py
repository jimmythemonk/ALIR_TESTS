# Generated by Django 4.1.7 on 2024-04-09 12:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("n5_lgr_backend", "0013_alter_testserialdata_cell_id"),
    ]

    operations = [
        migrations.AlterField(
            model_name="testserialdata",
            name="trumi_st",
            field=models.CharField(max_length=200),
        ),
    ]
