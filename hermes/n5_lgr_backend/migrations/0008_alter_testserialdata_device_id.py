# Generated by Django 4.1.7 on 2024-04-09 06:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("n5_lgr_backend", "0007_alter_testserialdata_options_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="testserialdata",
            name="device_id",
            field=models.CharField(max_length=200),
        ),
    ]
