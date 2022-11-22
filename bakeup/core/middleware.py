from django.conf import settings
from django.db import connection
from django_tenants.utils import get_public_schema_name, get_tenant_model

class TenantSettingsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        self.request = request
        self.overload_settings()
        response = self.get_response(request)
        return response

    def overload_settings(self):
        current_schema_obj = get_tenant_model().objects.get(schema_name=connection.schema_name)
        if hasattr(current_schema_obj, 'clientsetting'):
            client_settings = current_schema_obj.clientsetting
            settings.DEFAULT_FROM_EMAIL = client_settings.default_from_email
            settings.EMAIL_HOST = client_settings.email_host
            settings.EMAIL_HOST_PASSWORD = client_settings.email_host_password
            settings.EMAIL_HOST_USER = client_settings.email_host_user
            settings.EMAIL_PORT = client_settings.email_port
            settings.EMAIL_USE_TLS = client_settings.emaiL_use_tls
