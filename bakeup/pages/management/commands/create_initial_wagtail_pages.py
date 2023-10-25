from pathlib import Path

from django.contrib.contenttypes.models import ContentType
from django.core.files import File
from django.core.management.base import BaseCommand
from django.db import connection
from django_tenants.management.commands import InteractiveTenantOption
from wagtail.images.models import Image
from wagtail.models import Page, Site
from wagtailmenus.conf import settings as wagtailmenu_settings

from bakeup.pages.models import ContentPage, ShopPage

APP_DIR = Path(__file__).resolve().parent.parent.parent
FIXTURES_DIR = APP_DIR.joinpath("fixtures")


class Command(InteractiveTenantOption, BaseCommand):
    help = "Creates initial pages for the wagtail site"

    def _boolean_input(self, question, default=None):
        self.stdout.write(f"{question} ", ending="")
        result = input()
        if not result and default is not None:
            return default
        while not result or result[0].lower() not in "yn":
            self.stdout.write("Please answer yes or no: ", ending="")
            result = input()
        return result[0].lower() == "y"

    def _set_image(self, instance, attr_name, folder_path, img_path):
        """Helper to set images on models."""
        img_path = folder_path.joinpath(img_path)
        # Create and set the file if it does not yet exist.
        qs = Image.objects.filter(title=img_path.name)
        if not qs.exists():
            with open(img_path, "rb") as f:
                # setting name= is important. otherwise it uses the entire file path as
                # name, which leaks server filesystem structure to the outside.
                image_file = File(f, name=img_path.stem)
                image = Image(title=img_path.name, file=image_file.open())
                image.save()
        else:
            image = qs[0]
        setattr(instance, attr_name, image)
        instance.save()

    def _setup_root(self, tenant):
        Page.objects.exclude(id=1).delete()
        Site.objects.all().delete()
        page_content_type, created = ContentType.objects.get_or_create(
            model="page", app_label="wagtailcore"
        )
        root = Page.get_first_root_node()
        domain = tenant.get_primary_domain()
        shop_page_content_type = ContentType.objects.get_for_model(ShopPage)
        shop_page = ShopPage(
            title="Shop",
            draft_title="Shop",
            slug="shop",
            content_type=shop_page_content_type,
            show_in_menus=True,
            banner_text="<h1>Willkommen im {} Shop!</h1>".format(tenant.name),
            text_no_production_day="<h2>Aktuell sind keine Backtage geplant.</h2>",
        )
        root.add_child(instance=shop_page)
        folder_path = FIXTURES_DIR.joinpath("img")
        self._set_image(
            instance=shop_page,
            attr_name="banner_image",
            folder_path=folder_path,
            img_path="banner.jpg",
        )

        Site.objects.create(
            hostname=domain.domain,
            port="80",
            site_name=tenant.name,
            root_page=shop_page,
            is_default_site=True,
        )

    def _setup_default_pages(self, tenant):
        defaultpage_content_type = ContentType.objects.get_for_model(ContentPage)
        shop_page = ShopPage.objects.first()
        blocks = [
            {
                "type": "text",
                "value": {
                    "text": (
                        "<h1>Impressum</h1><b>{}<br/></b>Musterstraße 123 <br/>12345"
                        " Musterstadt</p><p><b>Kontakt:</b></p><ul><li>Telefon: +49 123"
                        " 4567890</li><li>E-Mail:"
                        " info@musterbackstube.de</li><li>Webseite: <a"
                        ' href="http://musterbackstube.de">musterbackstube.de</a></li></ul>'
                        .format(tenant.name)
                    ),
                    "alignment": "start",
                },
            }
        ]
        impressum = ContentPage(
            title="Impressum",
            draft_title="Impressum",
            slug="impressum",
            content_type=defaultpage_content_type,
            show_in_menus=True,
            content=blocks,
        )
        shop_page.add_child(instance=impressum)
        blocks = [
            {
                "type": "text",
                "value": {
                    "text": (
                        "<h1>Datenschutz</h1><h2>1. Datenschutz auf einen"
                        " Blick</h2><p>Unsere Datenschutzerklärung soll Ihnen einen"
                        " Überblick darüber verschaffen, wie wir Ihre personenbezogenen"
                        " Daten verarbeiten und schützen.</p><h3>1.1 Wer sind"
                        " wir?</h3><p><b>{}<br/></b><br>Musterstraße 123<br>12345"
                        " Musterstadt</p>Weitere Abschnitte und Informationen"
                        " einfügen<p>".format(tenant.name)
                    ),
                    "alignment": "start",
                },
            }
        ]
        privacy = ContentPage(
            title="Datenschutz",
            draft_title="Datenschutz",
            slug="datenschutz",
            content_type=defaultpage_content_type,
            show_in_menus=True,
            content=blocks,
        )
        shop_page.add_child(instance=privacy)
        blocks = [
            {
                "type": "text",
                "value": {
                    "text": "<h1>Unsere geplanten Backtage</h1>",
                    "alignment": "start",
                },
            },
            {"type": "production_days", "value": {"production_day_limit": None}},
        ]
        production_day = ContentPage(
            title="Backtage",
            draft_title="Backtage",
            slug="backtage",
            content_type=defaultpage_content_type,
            show_in_menus=True,
            content=blocks,
        )
        shop_page.add_child(instance=production_day)
        blocks = [
            {
                "type": "text",
                "value": {"text": "<h1>Unser Sortiment</h1>", "alignment": "start"},
            },
            {"type": "product_assortment", "value": {"only_planned_products": False}},
        ]
        assortment = ContentPage(
            title="Sortiment",
            draft_title="Sortiment",
            slug="sortiment",
            content_type=defaultpage_content_type,
            show_in_menus=True,
            content=blocks,
        )
        shop_page.add_child(instance=assortment)

    def _create_main_menu(self):
        site = Site.objects.all().first()
        menu_model = wagtailmenu_settings.models.MAIN_MENU_MODEL

        # create the german footer
        main_menu, created = menu_model.objects.get_or_create(
            site=site,
        )
        if not main_menu.get_menu_items_manager().exists():
            # create the menu items for each page needed
            item_manager = main_menu.get_menu_items_manager()
            item_class = item_manager.model
            item_list = []
            shop_page = ShopPage.objects.first()
            item_list.append(
                item_class(
                    menu=main_menu,
                    link_text="Shop",
                    link_page=shop_page,
                    sort_order=1,
                    allow_subnav=False,
                )
            )
            for i, slug in enumerate(["backtage", "sortiment"], start=2):
                page = ContentPage.objects.get(slug=slug)
                item_list.append(
                    item_class(
                        menu=main_menu,
                        link_text=page.title,
                        link_page=page,
                        sort_order=i,
                        allow_subnav=False,
                    )
                )
            item_manager.bulk_create(item_list)

    def _create_flat_menus(self):
        site = Site.objects.all()[0]
        menu_model = wagtailmenu_settings.models.FLAT_MENU_MODEL

        # create the german footer
        footer, created = menu_model.objects.get_or_create(
            site=site, handle="footer", title="Footer"
        )
        if not footer.get_menu_items_manager().exists():
            # create the menu items for each page needed
            item_manager = footer.get_menu_items_manager()
            item_class = item_manager.model
            item_list = []
            for i, slug in enumerate(["impressum", "datenschutz"], start=1):
                page = ContentPage.objects.get(slug=slug)
                item_list.append(
                    item_class(
                        menu=footer,
                        link_text=page.title,
                        link_page=page,
                        sort_order=i,
                        allow_subnav=False,
                    )
                )
            item_manager.bulk_create(item_list)

    def handle(self, *args, **options):
        tenant = self.get_tenant_from_options_or_interactive(**options)
        connection.set_tenant(tenant)
        do_create = self._boolean_input(
            "Would you really like to delete all existing site and page models? [y/N]",
            default=False,
        )
        if do_create:
            self._setup_root(tenant)
            self._setup_default_pages(tenant)
            # finally, create the menus
            self._create_main_menu()
            self._create_flat_menus()

        self.stdout.write(
            self.style.SUCCESS("All pages created for tenant {}".format(tenant))
        )
