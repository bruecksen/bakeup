from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "bakeup.core"

    def ready(self):
        import bakeup.core.signals  # noqa F401
