from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("appointments", "0003_allow_cancelled_slot_rebooking"),
    ]

    operations = [
        migrations.AddField(
            model_name="appointment",
            name="consultation_fee",
            field=models.DecimalField(
                max_digits=10, decimal_places=2, null=True, blank=True,
            ),
        ),
        migrations.AddField(
            model_name="appointment",
            name="currency_code",
            field=models.CharField(max_length=3, blank=True, default=""),
        ),
    ]
