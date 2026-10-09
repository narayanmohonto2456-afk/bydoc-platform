"""Public, bounded clinic lookup around a user-supplied point."""

from math import asin, cos, degrees, radians, sin, sqrt

from django.db.models import Exists, OuterRef, Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import permissions, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.clinics.models import Clinic
from apps.doctors.models import DoctorClinicAffiliation, DoctorProfile, DoctorRegistration


EARTH_RADIUS_KM = 6371.0088


class NearbyQuerySerializer(serializers.Serializer):
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)
    radius_km = serializers.FloatField(min_value=1, max_value=30, default=15)


class NearbyClinicSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    address = serializers.CharField()
    locality = serializers.CharField()
    district = serializers.CharField()
    state = serializers.CharField()
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    distance_km = serializers.FloatField()


def distance_km(latitude, longitude, clinic_latitude, clinic_longitude):
    lat1, lon1, lat2, lon2 = map(radians, (latitude, longitude, clinic_latitude, clinic_longitude))
    a = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(min(1, sqrt(a)))


class NearbyClinicView(APIView):
    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()

    @extend_schema(
        parameters=[
            OpenApiParameter("latitude", float, required=True),
            OpenApiParameter("longitude", float, required=True),
            OpenApiParameter("radius_km", float, required=False),
        ],
        responses={200: NearbyClinicSerializer(many=True)},
    )
    def get(self, request):
        query = NearbyQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        latitude = query.validated_data["latitude"]
        longitude = query.validated_data["longitude"]
        radius = query.validated_data["radius_km"]

        # Bounding box reduces the rows that need exact great-circle distance.
        latitude_span = degrees(radius / EARTH_RADIUS_KM)
        longitude_span = min(180, latitude_span / max(0.01, cos(radians(latitude))))
        west = longitude - longitude_span
        east = longitude + longitude_span
        longitude_filter = Q(longitude__gte=max(-180, west), longitude__lte=min(180, east))
        if west < -180:
            longitude_filter |= Q(longitude__gte=west + 360)
        if east > 180:
            longitude_filter |= Q(longitude__lte=east - 360)

        bookable_doctor = DoctorClinicAffiliation.objects.filter(
            clinic_id=OuterRef("pk"),
            status=DoctorClinicAffiliation.Status.ACTIVE,
            accepts_online_bookings=True,
            doctor__status=DoctorProfile.Status.ACTIVE,
            doctor__registrations__verification_status=DoctorRegistration.VerificationStatus.VERIFIED,
        ).filter(
            Q(doctor__registrations__valid_until__isnull=True)
            | Q(doctor__registrations__valid_until__gte=timezone.localdate())
        )
        clinics = Clinic.objects.active().filter(
            longitude_filter,
            latitude__isnull=False,
            longitude__isnull=False,
            latitude__gte=latitude - latitude_span,
            latitude__lte=latitude + latitude_span,
        ).annotate(has_bookable_doctor=Exists(bookable_doctor)).filter(has_bookable_doctor=True)

        results = []
        for clinic in clinics.iterator():
            distance = distance_km(latitude, longitude, float(clinic.latitude), float(clinic.longitude))
            if distance <= radius:
                results.append({
                    "id": clinic.pk,
                    "name": clinic.name,
                    "address": clinic.address_line_1,
                    "locality": clinic.locality,
                    "district": clinic.district,
                    "state": clinic.state,
                    "latitude": float(clinic.latitude),
                    "longitude": float(clinic.longitude),
                    "distance_km": round(distance, 1),
                })
        results.sort(key=lambda item: (item["distance_km"], item["name"]))
        response = Response(NearbyClinicSerializer(results[:50], many=True).data)
        response["Cache-Control"] = "private, no-store"
        return response
