"""Apply the API's shared authentication limits to the Django admin login."""

from math import ceil

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters
from rest_framework.exceptions import Throttled

from .rate_limits import AuthenticationTemporarilyUnavailable, client_address, consume_limit


@never_cache
@csrf_protect
@sensitive_post_parameters("password")
def admin_login(request):
    if request.method == "POST":
        identifier = get_user_model().normalize_username(request.POST.get("username", "")).casefold()
        try:
            consume_limit("login_ip", client_address(request))
            consume_limit("login_account", identifier)
        except (Throttled, AuthenticationTemporarilyUnavailable) as error:
            response = JsonResponse({"detail": str(error.detail)}, status=error.status_code)
            if isinstance(error, Throttled):
                response["Retry-After"] = str(ceil(error.wait))
            return response
    return admin.site.login(request)
