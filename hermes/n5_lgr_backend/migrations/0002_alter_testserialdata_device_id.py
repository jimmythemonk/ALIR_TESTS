# Generated by Django 4.1.7 on 2024-04-08 12:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("n5_lgr_backend", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="testserialdata",
            name="device_id",
            field=models.CharField(max_length=200),
        ),
    ]
