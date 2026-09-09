from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("appointments", "0002_appointment_booking_request_id_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="appointment",
            name="slot",
            field=models.ForeignKey(
                to="appointments.appointmentslot",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="appointments",
            ),
        ),
        migrations.AddConstraint(
            model_name="appointment",
            constraint=models.UniqueConstraint(
                fields=["slot"],
                condition=~models.Q(status="cancelled"),
                name="unique_non_cancelled_slot_appt",
            ),
        ),
    ]
