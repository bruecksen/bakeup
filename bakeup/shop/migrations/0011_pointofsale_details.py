from django.db import migrations, models


def keep_old_address(apps, schema_editor):
    # Runs once per tenant schema. The old address is one free text that can't
    # be split into street and city, so it becomes the description.
    PointOfSale = apps.get_model("shop", "PointOfSale")
    # The default manager would leave out archived points of sale.
    for point_of_sale in PointOfSale._base_manager.exclude(address=None):
        address = (point_of_sale.address.address or "").strip()
        if address:
            PointOfSale._base_manager.filter(pk=point_of_sale.pk).update(
                description=address
            )


class Migration(migrations.Migration):
    dependencies = [
        ("contrib", "0003_alter_note_options"),
        ("shop", "0010_pointofsale_is_internal"),
    ]

    operations = [
        migrations.AddField(
            model_name="pointofsale",
            name="street",
            field=models.CharField(
                blank=True, max_length=100, null=True, verbose_name="Street"
            ),
        ),
        migrations.AddField(
            model_name="pointofsale",
            name="street_number",
            field=models.CharField(
                blank=True, max_length=10, null=True, verbose_name="Street Number"
            ),
        ),
        migrations.AddField(
            model_name="pointofsale",
            name="postal_code",
            field=models.CharField(
                blank=True, max_length=10, null=True, verbose_name="Postal Code"
            ),
        ),
        migrations.AddField(
            model_name="pointofsale",
            name="city",
            field=models.CharField(
                blank=True, max_length=100, null=True, verbose_name="City"
            ),
        ),
        migrations.AddField(
            model_name="pointofsale",
            name="description",
            field=models.TextField(blank=True, verbose_name="Description"),
        ),
        migrations.AddField(
            model_name="pointofsale",
            name="latitude",
            field=models.DecimalField(
                blank=True,
                decimal_places=6,
                max_digits=9,
                null=True,
                verbose_name="Latitude",
            ),
        ),
        migrations.AddField(
            model_name="pointofsale",
            name="longitude",
            field=models.DecimalField(
                blank=True,
                decimal_places=6,
                max_digits=9,
                null=True,
                verbose_name="Longitude",
            ),
        ),
        migrations.RunPython(keep_old_address, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="pointofsale",
            name="address",
        ),
        # The opening hours, so far only editable in the Django admin, become
        # the pick-up times of the point of sale and keep their rows.
        migrations.RenameModel(
            old_name="PointOfSaleOpeningHour",
            new_name="PointOfSalePickupTime",
        ),
        migrations.AlterModelOptions(
            name="pointofsalepickuptime",
            options={"ordering": ("day_of_the_week", "from_time")},
        ),
        migrations.AlterField(
            model_name="pointofsalepickuptime",
            name="point_of_sale",
            field=models.ForeignKey(
                on_delete=models.deletion.CASCADE,
                related_name="pickup_times",
                to="shop.pointofsale",
            ),
        ),
        migrations.AlterField(
            model_name="pointofsalepickuptime",
            name="day_of_the_week",
            field=models.PositiveSmallIntegerField(
                choices=[
                    (0, "Monday"),
                    (1, "Tuesday"),
                    (2, "Wednesday"),
                    (3, "Thursday"),
                    (4, "Friday"),
                    (5, "Saturday"),
                    (6, "Sunday"),
                ],
                verbose_name="Weekday",
            ),
        ),
        migrations.AlterField(
            model_name="pointofsalepickuptime",
            name="from_time",
            field=models.TimeField(verbose_name="From"),
        ),
        migrations.AlterField(
            model_name="pointofsalepickuptime",
            name="to_time",
            field=models.TimeField(verbose_name="Until"),
        ),
    ]
