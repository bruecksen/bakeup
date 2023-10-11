from django.conf import settings


class TenantSettings:
    @classmethod
    def overload_settings(cls, tenant, request=None):
        if hasattr(tenant, "clientsetting"):
            print("loading client settings")
            client_settings = tenant.clientsetting
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
        if request:
            settings.WAGTAILADMIN_BASE_URL = tenant.get_absolute_primary_domain(request)
