from rest_framework.permissions import BasePermission

from .models import StaffGrant


def has_role(user, role):
    return bool(
        user and user.is_authenticated and user.is_active
        and (user.is_superuser or StaffGrant.objects.filter(user=user, role=role, active=True).exists())
    )


def roles_for(user):
    if not user or not user.is_authenticated or not user.is_active:
        return []
    if user.is_superuser:
        return list(StaffGrant.Role.values)
    return list(StaffGrant.objects.filter(user=user, active=True).values_list("role", flat=True))


def has_any_role(user):
    return bool(roles_for(user))


class IsOperationsStaff(BasePermission):
    def has_permission(self, request, view):
        return has_any_role(request.user)
