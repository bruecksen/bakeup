from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import connection
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.utils import translation
from django.utils.deprecation import MiddlewareMixin
from django_tenants.utils import get_tenant_model


class TenantSettingsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        self.request = request
        self.overload_settings()
        response = self.get_response(request)
        return response

    def overload_settings(self):
        try:
            current_schema_obj = get_tenant_model().objects.get(
                schema_name=connection.schema_name
            )
            if hasattr(current_schema_obj, "clientsetting"):
                client_settings = current_schema_obj.clientsetting
                settings.DEFAULT_FROM_EMAIL = client_settings.default_from_email
                settings.SERVER_EMAIL = client_settings.default_from_email
                settings.EMAIL_HOST = client_settings.email_host
                settings.EMAIL_HOST_PASSWORD = client_settings.email_host_password
                settings.EMAIL_HOST_USER = client_settings.email_host_user
                settings.EMAIL_PORT = client_settings.email_port
                settings.EMAIL_USE_TLS = client_settings.email_use_tls
                settings.ACCOUNT_EMAIL_VERIFICATION = (
                    client_settings.account_email_verification
                )
            settings.WAGTAILADMIN_BASE_URL = (
                current_schema_obj.get_absolute_primary_domain(self.request)
            )
        except ObjectDoesNotExist:
            pass


class PersistentFiltersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        path = request.path_info
        if path not in settings.PERSISTENT_FILTERS_URLS:
            return response

        query_string = request.META["QUERY_STRING"]

        for exclude_query_string in settings.PERSISTENT_FILTERS_EXCLUDE_QUERY_STRINGS:
            query_string = query_string.replace(exclude_query_string, "")

        if "reset-filters" in request.META["QUERY_STRING"]:
            response = redirect(path)
            response.delete_cookie("filters{}".format(path.replace("/", "_")))
            return response

        if len(query_string) > 0:
            response.set_cookie(
                key="filters{}".format(path.replace("/", "_")),
                value=query_string,
                max_age=28800,
            )
            return response

        if len(query_string) == 0 and request.COOKIES.get(
            "filters{}".format(path.replace("/", "_"))
        ):
            redirect_to = (
                request.path
                + "?"
                + request.COOKIES.get("filters{}".format(path.replace("/", "_")))
            )
            return HttpResponseRedirect(redirect_to)

        return response


class LocaleMiddleware(MiddlewareMixin):
    """
    This is a very simple middleware that sets the language to the language that is defined in the client settings.
    """

    def process_request(self, request):
        try:
            current_schema_obj = get_tenant_model().objects.get(
                schema_name=connection.schema_name
            )
            if hasattr(current_schema_obj, "clientsetting"):
                translation.activate(current_schema_obj.clientsetting.language_default)
                request.LANGUAGE_CODE = translation.get_language()
        except ObjectDoesNotExist:
            pass

    def process_response(self, request, response):
        translation.deactivate()
        return response
