# Generated by Django 2.2.3 on 2019-07-17 08:48

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("robbit", "0003_tile_parent")]

    operations = [
        migrations.AlterField(
            model_name="tile",
            name="depth",
            field=models.IntegerField(
                db_index=True,
                validators=[
                    django.core.validators.MinValueValidator(
                        0,
                        message="Depth cannot be lower than 0 as it is already a full-earth tile",
                    ),
                    django.core.validators.MinValueValidator(
                        19,
                        message="Max depth is 19 because more would not be useful (see documentation)",
                    ),
                ],
            ),
        )
    ]
