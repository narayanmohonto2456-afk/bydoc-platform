from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("appointments", "0004_appointment_fee_snapshot")]

    operations = [
        migrations.AddField(
            model_name="appointmentslot",
            name="schedule_blocked",
            field=models.BooleanField(default=False),
        ),
    ]
