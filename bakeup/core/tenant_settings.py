from django.conf import settings

from config.settings.base import env


class TenantSettings:
    @classmethod
    def overload_settings(cls, tenant, request=None):
        if hasattr(tenant, "clientsetting"):
            client_settings = tenant.clientsetting
            if client_settings.default_from_email:
                settings.DEFAULT_FROM_EMAIL = client_settings.default_from_email
                settings.SERVER_EMAIL = client_settings.default_from_email
                settings.EMAIL_HOST = client_settings.email_host
                settings.EMAIL_HOST_PASSWORD = client_settings.email_host_password
                settings.EMAIL_HOST_USER = client_settings.email_host_user
                settings.EMAIL_PORT = client_settings.email_port
                settings.EMAIL_USE_TLS = client_settings.email_use_tls
            else:
                settings.EMAIL_HOST = env("DJANGO_EMAIL_HOST", default=None)
                settings.EMAIL_HOST_PASSWORD = env(
                    "DJANGO_EMAIL_HOST_PASSWORD", default=None
                )
                settings.EMAIL_HOST_USER = env("DJANGO_EMAIL_HOST_USER", default=None)
                settings.EMAIL_PORT = env("DJANGO_EMAIL_PORT", default=587)
                settings.EMAIL_USE_TLS = env("DJANGO_EMAIL_USE_TLS", default=True)
            if client_settings.account_email_verification:
                settings.ACCOUNT_EMAIL_VERIFICATION = (
                    client_settings.account_email_verification
                )

        if request:
            settings.WAGTAILADMIN_BASE_URL = tenant.default_full_url
