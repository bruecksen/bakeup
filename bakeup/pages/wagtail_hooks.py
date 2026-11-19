from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from wagtail import hooks
from wagtail.admin.menu import MenuItem
from wagtail.admin.ui.sidebar import LinkMenuItem
from wagtailmenus.models import MainMenu

from bakeup.pages.models import BlockReferencePage, GeneralSettings


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


class BlockReferenceMenuItem(MenuItem):
    """
    Links to the block reference page on the site, if the tenant has one.
    Menu items are created once for all tenants, so the URL is looked up per
    request.
    """

    def _get_page(self, request):
        if not hasattr(request, "_block_reference_page"):
            request._block_reference_page = BlockReferencePage.objects.live().first()
        return request._block_reference_page

    def is_shown(self, request):
        return self._get_page(request) is not None

    def render_component(self, request):
        return LinkMenuItem(
            self.name,
            self.label,
            self._get_page(request).get_url(request),
            icon_name=self.icon_name,
            classname=self.classname,
            attrs={"target": "_blank"},
        )


@hooks.register("register_admin_menu_item")
def register_block_reference_menu_item():
    return BlockReferenceMenuItem(
        _("Block overview"),
        url="",
        name="block-reference",
        icon_name="placeholder",
        order=250,
    )


@hooks.register("register_icons")
def register_block_icons(icons):
    return icons + ["pages/icons/spacer.svg", "pages/icons/line.svg"]
