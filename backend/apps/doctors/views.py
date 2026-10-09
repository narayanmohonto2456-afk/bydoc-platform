from django.db.models import Exists, OuterRef, Prefetch, Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, serializers

from apps.clinics.models import Clinic
from apps.clinics.views import PublicClinicSerializer, PublicDirectoryPagination
from apps.organizations.models import Organization

from .models import (
    DoctorClinicAffiliation, DoctorProfile, DoctorRegistration, Language, Specialty,
)


def public_affiliations():
    return DoctorClinicAffiliation.objects.filter(
        status=DoctorClinicAffiliation.Status.ACTIVE,
        clinic__status=Clinic.Status.ACTIVE,
        clinic__organization__status=Organization.Status.ACTIVE,
    )


class DoctorSearchParameters(serializers.Serializer):
    q = serializers.CharField(required=False, max_length=100, allow_blank=False)
    specialty = serializers.SlugField(required=False, max_length=120)
    language = serializers.CharField(required=False, max_length=10, allow_blank=False)
    clinic_id = serializers.UUIDField(required=False)
    state = serializers.CharField(required=False, max_length=120, allow_blank=False)
    district = serializers.CharField(required=False, max_length=120, allow_blank=False)
    online_booking = serializers.BooleanField(required=False)


class PublicAffiliationSerializer(serializers.ModelSerializer):
    clinic = PublicClinicSerializer(read_only=True)

    class Meta:
        model = DoctorClinicAffiliation
        fields = ("clinic", "consultation_fee", "currency_code", "accepts_online_bookings")
        read_only_fields = fields


class PublicDoctorSerializer(serializers.ModelSerializer):
    primary_specialty = serializers.SlugRelatedField(read_only=True, slug_field="name")
    specialties = serializers.SlugRelatedField(read_only=True, many=True, slug_field="name")
    languages = serializers.SlugRelatedField(read_only=True, many=True, slug_field="code")
    clinics = PublicAffiliationSerializer(source="public_affiliations", many=True, read_only=True)

    class Meta:
        model = DoctorProfile
        fields = (
            "id", "display_name", "professional_summary",
            "experience_start_year", "primary_specialty", "specialties",
            "languages", "clinics",
        )
        read_only_fields = fields


def public_doctors(affiliation_filters=None):
    affiliations = public_affiliations().filter(doctor_id=OuterRef("pk"))
    if affiliation_filters:
        affiliations = affiliations.filter(**affiliation_filters)
    verified = DoctorRegistration.objects.filter(
        doctor_id=OuterRef("pk"),
        verification_status=DoctorRegistration.VerificationStatus.VERIFIED,
    ).filter(Q(valid_until__isnull=True) | Q(valid_until__gte=timezone.localdate()))
    return (
        DoctorProfile.objects.filter(status=DoctorProfile.Status.ACTIVE)
        .alias(has_registration=Exists(verified), has_clinic=Exists(affiliations))
        .filter(has_registration=True, has_clinic=True)
        .select_related("primary_specialty")
        .prefetch_related(
            "specialties", "languages",
            Prefetch(
                "clinic_affiliations",
                queryset=public_affiliations().select_related("clinic").order_by("clinic__name", "pk"),
                to_attr="public_affiliations",
            ),
        )
    )


@extend_schema(parameters=[DoctorSearchParameters])
class PublicDoctorListView(generics.ListAPIView):
    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()
    serializer_class = PublicDoctorSerializer
    pagination_class = PublicDirectoryPagination

    def get_queryset(self):
        params = DoctorSearchParameters(data=dict(self.request.query_params.items()))
        params.is_valid(raise_exception=True)
        filters = params.validated_data
        affiliation_filters = {}
        for name, lookup in (
            ("clinic_id", "clinic_id"),
            ("state", "clinic__state__iexact"),
            ("district", "clinic__district__iexact"),
            ("online_booking", "accepts_online_bookings"),
        ):
            if name in filters:
                affiliation_filters[lookup] = filters[name]

        queryset = public_doctors(affiliation_filters)
        if term := filters.get("q"):
            queryset = queryset.filter(display_name__icontains=term)
        if specialty := filters.get("specialty"):
            specialty_match = Specialty.objects.filter(
                doctor_profiles__id=OuterRef("pk"), slug__iexact=specialty, is_active=True,
            )
            primary_match = Q(primary_specialty__slug__iexact=specialty, primary_specialty__is_active=True)
            queryset = queryset.alias(matched_specialty=Exists(specialty_match)).filter(
                primary_match | Q(matched_specialty=True)
            )
        if language := filters.get("language"):
            language_match = Language.objects.filter(
                doctor_profiles__id=OuterRef("pk"), code__iexact=language, is_active=True,
            )
            queryset = queryset.alias(matched_language=Exists(language_match)).filter(matched_language=True)
        return queryset.order_by("display_name", "pk")


class PublicDoctorDetailView(generics.RetrieveAPIView):
    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()
    serializer_class = PublicDoctorSerializer
    lookup_url_kwarg = "doctor_id"

    def get_queryset(self):
        return public_doctors()
