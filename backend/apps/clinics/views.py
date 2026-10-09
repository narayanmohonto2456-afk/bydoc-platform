from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, serializers
from rest_framework.pagination import PageNumberPagination

from .models import Clinic


class PublicDirectoryPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class ClinicSearchParameters(serializers.Serializer):
    q = serializers.CharField(required=False, max_length=100, allow_blank=False)
    state = serializers.CharField(required=False, max_length=120, allow_blank=False)
    district = serializers.CharField(required=False, max_length=120, allow_blank=False)
    wheelchair_accessible = serializers.BooleanField(required=False)


class PublicClinicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Clinic
        fields = (
            "id", "name", "address_line_1", "address_line_2",
            "locality", "district", "state", "postal_code",
            "latitude", "longitude", "timezone", "wheelchair_accessible",
            "has_accessible_restroom", "has_waiting_area", "accepts_walk_ins",
        )
        read_only_fields = fields


@extend_schema(parameters=[ClinicSearchParameters])
class PublicClinicListView(generics.ListAPIView):
    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()
    serializer_class = PublicClinicSerializer
    pagination_class = PublicDirectoryPagination

    def get_queryset(self):
        params = ClinicSearchParameters(data=dict(self.request.query_params.items()))
        params.is_valid(raise_exception=True)
        filters = params.validated_data
        queryset = Clinic.objects.active()
        if term := filters.get("q"):
            queryset = queryset.filter(
                Q(name__icontains=term)
                | Q(locality__icontains=term)
                | Q(district__icontains=term)
            )
        for field in ("state", "district", "wheelchair_accessible"):
            if field in filters:
                value = filters[field]
                lookup = field if field == "wheelchair_accessible" else f"{field}__iexact"
                queryset = queryset.filter(**{lookup: value})
        return queryset.order_by("name", "pk")


class PublicClinicDetailView(generics.RetrieveAPIView):
    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()
    serializer_class = PublicClinicSerializer
    lookup_url_kwarg = "clinic_id"

    def get_queryset(self):
        return Clinic.objects.active()
