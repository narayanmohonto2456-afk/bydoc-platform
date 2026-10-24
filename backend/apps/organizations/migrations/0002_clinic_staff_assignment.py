import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def backfill_single_clinic_receptionists(apps, schema_editor):
    Membership = apps.get_model("organizations", "OrganizationMembership")
    Assignment = apps.get_model("organizations", "ClinicStaffAssignment")
    Clinic = apps.get_model("clinics", "Clinic")
    for membership in Membership.objects.filter(role="receptionist", status="active").iterator():
        clinics = list(
            Clinic.objects.filter(organization_id=membership.organization_id)
            .values_list("id", flat=True)[:2]
        )
        if len(clinics) == 1:
            Assignment.objects.get_or_create(
                membership_id=membership.pk, clinic_id=clinics[0],
                defaults={"reason": "Preserved existing single-clinic access"},
            )


class Migration(migrations.Migration):
    dependencies = [
        ("organizations", "0001_initial"),
        ("clinics", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ClinicStaffAssignment",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("is_active", models.BooleanField(default=True)),
                ("reason", models.CharField(max_length=250, blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("assigned_by", models.ForeignKey(
                    to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT,
                    null=True, blank=True, related_name="clinic_assignments_made",
                )),
                ("clinic", models.ForeignKey(
                    to="clinics.clinic", on_delete=django.db.models.deletion.PROTECT,
                    related_name="staff_assignments",
                )),
                ("membership", models.ForeignKey(
                    to="organizations.organizationmembership", on_delete=django.db.models.deletion.PROTECT,
                    related_name="clinic_assignments",
                )),
            ],
            options={"db_table": "organizations_clinic_staff_assignment"},
        ),
        migrations.AddConstraint(
            model_name="clinicstaffassignment",
            constraint=models.UniqueConstraint(
                fields=["membership", "clinic"], name="unique_membership_clinic_assignment",
            ),
        ),
        migrations.AddIndex(
            model_name="clinicstaffassignment",
            index=models.Index(fields=["clinic", "is_active"], name="clinic_staff_active_idx"),
        ),
        migrations.RunPython(backfill_single_clinic_receptionists, migrations.RunPython.noop),
    ]
