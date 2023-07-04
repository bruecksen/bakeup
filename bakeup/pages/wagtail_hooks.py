from django.urls import reverse
from django.utils.translation import ugettext_lazy as _

from wagtailmenus.models import MainMenu

from wagtail import hooks


@hooks.register("construct_settings_menu")
def hide_user_menu_item(request, menu_items):
    exclude_item_list = ('benutzer', 'gruppen', 'users', 'groups', 'workflows', 'workflow-tasks')
    menu_items[:] = [item for item in menu_items if item.name not in exclude_item_list]


@hooks.register('construct_main_menu')
def hide_snippets_menu_item(request, menu_items):
    exclude_item_list = ('berichte', 'reports')
    menu_items[:] = [item for item in menu_items if item.name not in exclude_item_list]


@hooks.register('menus_modify_primed_menu_items')
def add_abo_menu_item(menu_items, request, menu_instance, **kwargs):
    if request.user.is_authenticated and isinstance(menu_instance, MainMenu) and request.user.customer.order_templates.active().exists():
        menu_items.extend([
            {"text": _("Abo"),  "href": reverse("shop:order-template-list")},
        ])
    return menu_items