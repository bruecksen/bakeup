from django.apps import AppConfig


class ShopConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'bakeup.shop'


    def ready(self):
        import bakeup.shop.signals  # noqa F401
        pass
