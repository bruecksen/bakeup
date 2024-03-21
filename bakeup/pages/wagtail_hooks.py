from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from wagtail import hooks
from wagtailmenus.models import MainMenu

from bakeup.pages.models import GeneralSettings


@hooks.register("construct_settings_menu")
def hide_user_menu_item(request, menu_items):
    exclude_item_list = (
        "benutzer",
        "gruppen",
        "users",
        "groups",
        "workflows",
        "workflow-tasks",
    )
    menu_items[:] = [item for item in menu_items if item.name not in exclude_item_list]


@hooks.register("construct_main_menu")
def hide_snippets_menu_item(request, menu_items):
    exclude_item_list = ("berichte", "reports")
    menu_items[:] = [item for item in menu_items if item.name not in exclude_item_list]


@hooks.register("menus_modify_primed_menu_items")
def add_abo_menu_item(menu_items, request, menu_instance, **kwargs):
    general_settings = GeneralSettings.load(request_or_site=request)
    if request.user.is_authenticated and isinstance(menu_instance, MainMenu):
        if general_settings.abo_menu_item == GeneralSettings.Visibility.NEVER:
            return menu_items
        elif general_settings.abo_menu_item == GeneralSettings.Visibility.ALWAYS:
            menu_items.extend(
                [
                    {"text": _("Abo"), "href": reverse("shop:order-template-list")},
                ]
            )
        elif (
            general_settings.abo_menu_item == GeneralSettings.Visibility.AUTOMATICALLY
            and request.user.customer.order_templates.active().exists()
        ):
            menu_items.extend(
                [
                    {"text": _("Abo"), "href": reverse("shop:order-template-list")},
                ]
            )
    return menu_items
