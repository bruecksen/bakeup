from django.conf import settings
from django.utils.module_loading import import_string

DEFAULT_NEWSLETTER_BACKEND = "newsletter.backend.SMTPEmailBackend"


def get_backend():
    backend_class = import_string(
        getattr(settings, "WAGTAIL_NEWSLETTER_BACKEND", DEFAULT_NEWSLETTER_BACKEND)
    )
    return backend_class()
