from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class UsersConfig(AppConfig):
    name = "bakeup.users"
    verbose_name = _("Users")

    def ready(self):
        import bakeup.users.signals  # noqa F401
