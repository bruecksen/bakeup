from datetime import date, timedelta
from pathlib import Path
from random import randint

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django_tenants.management.commands import InteractiveTenantOption
from wagtail.images.models import Image
from wagtail.models import Page, Site
from wagtailmenus.conf import settings as wagtailmenu_settings

from bakeup.core.models import ClientSetting
from bakeup.pages.models import BrandSettings, ContentPage, ShopPage
from bakeup.shop.models import ProductionDay, ProductionDayProduct
from bakeup.workshop.models import Product, ProductionPlan

APP_DIR = Path(__file__).resolve().parent.parent.parent
FIXTURES_DIR = APP_DIR.joinpath("fixtures")

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
STATIC_DIR = ROOT_DIR.joinpath("static")


# yellow: #ffff00
# magenta: #ff00ff
# cyan: #00ffff
# gray: #f8f9fa
# dark: #212529


class Command(InteractiveTenantOption, BaseCommand):
    help = "Creates initial demo pages for the wagtail site"

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--noinput",
            "--no-input",
            action="store_false",
            dest="interactive",
            help="Do NOT prompt the user for input of any kind.",
        )

    def set_options(self, **options):
        """
        Set instance variables based on an options dict
        """
        self.interactive = options["interactive"]

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
        blocks = [
            {"type": "hr", "value": {}},
            {
                "type": "column11",
                "value": {
                    "left": [
                        {
                            "type": "text",
                            "value": {
                                "text": (
                                    "<p>Hier könnte ein schöner kurzer Text stehen, der"
                                    " erklärt warum Ihr so tolles Brot backt: </p><p>In"
                                    " unserer Backstube verbinden wir Leidenschaft,"
                                    " Handwerkskunst und sorgfältig ausgewählte"
                                    " Zutaten, um ein einzigartiges Brot zu kreieren,"
                                    " das nicht nur köstlich schmeckt, sondern auch"
                                    " ernährungsphysiologisch wertvoll ist. Unser Teig"
                                    " reift langsam, um die Aromen zu intensivieren und"
                                    " eine perfekte Textur zu gewährleisten. Wir setzen"
                                    " auf hochwertiges Mehl, natürliche Hefen und"
                                    " verzichten auf künstliche Zusätze. Das Ergebnis"
                                    " ist ein Brot, das nicht nur den Gaumen verwöhnt,"
                                    " sondern auch den Ansprüchen an gesunde Ernährung"
                                    " gerecht wird. Bei jedem Bissen schmeckt man die"
                                    " Liebe zum Handwerk und die Hingabe zu qualitativ"
                                    " hochwertigem Brot. Willkommen in der Welt des"
                                    " außergewöhnlichen Geschmacks und der"
                                    " handgemachten Perfektion.</p>"
                                ),
                                "alignment": "start",
                            },
                        }
                    ],
                    "right": [
                        {"type": "video", "value": "https://youtu.be/cUdZebtbd0o"}
                    ],
                },
            },
        ]
        banner_cta = [
            {
                "type": "buttons",
                "value": {
                    "link": {"target": [{"type": "link", "value": "/workshop/"}]},
                    "text": "Jetzt anmelden und ausprobieren!",
                },
            }
        ]
        shop_page = ShopPage(
            title="Shop",
            draft_title="Shop",
            slug="shop",
            content_type=shop_page_content_type,
            show_in_menus=True,
            banner_cta=banner_cta,
            banner_position="center",
            banner_text=(
                "<h1>Herzlich Willkommen<br> auf der Demo-Seite von"
                " bakeup!</h1><br><br><h2>Auf unserer Demo-Seite kannst du direkt"
                " ausprobieren, wie unsere Software deiner Bäckerei helfen kann,"
                " Bestellungen abzuwickeln und deine Backstube zu"
                " organisieren.</h2><br>"
            ),
            text_no_production_day=(
                "<h2>Aktuell sind noch keine Backtage geplant.</h2><p>Willst du"
                " vielleicht einen ersten <a href='/workshop/'>Backtag</a> im Workshop"
                " anlegen und veröffentlichen?</p>"
            ),
            content=blocks,
        )
        root.add_child(instance=shop_page)
        folder_path = FIXTURES_DIR.joinpath("img")
        self._set_image(
            instance=shop_page,
            attr_name="banner_image",
            folder_path=folder_path,
            img_path="banner-demo.jpg",
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
        about_us = ContentPage(
            title="Über uns",
            draft_title="Über uns",
            slug="uber-uns",
            content_type=defaultpage_content_type,
            show_in_menus=True,
            content=[],
        )
        shop_page.add_child(instance=about_us)
        blocks = [
            {
                "type": "text",
                "value": {
                    "text": (
                        "<h1>Unsere Backstube</h1><p>Hier kann ein toller Text über die"
                        " Backstube stehen!</p>"
                    ),
                    "alignment": "start",
                },
            },
        ]
        backstube = ContentPage(
            title="Backstube",
            draft_title="Backstube",
            slug="backstube",
            content_type=defaultpage_content_type,
            show_in_menus=True,
            content=blocks,
        )
        about_us.add_child(instance=backstube)
        blocks = [
            {
                "type": "text",
                "value": {
                    "text": (
                        "<h1>Unsere Lieranten</h1><p>Hier kann ein toller Text über die"
                        " Backstube stehen!</p>"
                    ),
                    "alignment": "start",
                },
            },
        ]
        lieferanten = ContentPage(
            title="Lieferanten",
            draft_title="Lieferanten",
            slug="lieferanten",
            content_type=defaultpage_content_type,
            show_in_menus=True,
            content=blocks,
        )
        about_us.add_child(instance=lieferanten)

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
            page = ContentPage.objects.get(slug="uber-uns")
            item_list.append(
                item_class(
                    menu=main_menu,
                    link_text=page.title,
                    link_page=page,
                    sort_order=4,
                    allow_subnav=True,
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

    def _create_branding(self):
        folder_path = STATIC_DIR.joinpath("images")
        brand_settings = BrandSettings._get_or_create()
        brand_settings.is_brand_theme_activated = True
        brand_settings.primary_color = "#ff00ff"
        brand_settings.secondary_color = "#00ffff"
        brand_settings.light_color = "#e9ecef"
        brand_settings.dark_color = "#212529"
        self._set_image(
            instance=brand_settings,
            attr_name="logo",
            folder_path=folder_path,
            img_path="logo.png",
        )
        brand_settings.save()

    def _create_settings(self, tenant):
        client_setting, created = ClientSetting.objects.get_or_create(client=tenant)
        client_setting.default_from_email = settings.DEFAULT_FROM_EMAIL
        client_setting.email_host = settings.EMAIL_HOST
        client_setting.email_host_password = settings.EMAIL_HOST_PASSWORD
        client_setting.email_host_user = settings.EMAIL_HOST_USER
        client_setting.email_port = settings.EMAIL_PORT
        client_setting.email_use_tls = True
        client_setting.show_full_name_delivery_bill = True
        client_setting.show_remaining_products = True
        client_setting.user_registration_fields = [
            "first_name",
            "last_name",
            "point_of_sale",
            "street",
            "street_number",
            "postal_code",
            "city",
            "telephone_number",
        ]
        client_setting.save()

    def _create_future_production_day(self):
        production_day, created = ProductionDay.objects.get_or_create(
            day_of_sale=date.today() + timedelta(days=10),
            defaults={
                "description": (
                    "Unser nächster Demo Backtag kommt schon bald. Wir freuen uns wenn"
                    " du dabei bist!"
                )
            },
        )
        for product in Product.objects.filter(pk__in=[835, 23, 1390]):
            ProductionDayProduct.objects.create(
                product=product,
                max_quantity=randint(10, 20),
                production_day=production_day,
                is_published=True,
            )
        production_day.create_or_update_production_plans(
            state=ProductionPlan.State.PLANNED, create_max_quantity=True
        )

    def handle(self, *args, **options):
        tenant = self.get_tenant_from_options_or_interactive(**options)
        self.set_options(**options)
        connection.set_tenant(tenant)
        if self.interactive:
            do_create = self._boolean_input(
                "Would you really like to delete all existing site and page models?"
                " [y/N]",
                default=False,
            )
            if not do_create:
                raise CommandError("Collecting static files cancelled.")

        self._setup_root(tenant)
        self._setup_default_pages(tenant)
        # finally, create the menus
        self._create_main_menu()
        self._create_flat_menus()
        self._create_branding()
        self._create_settings(tenant)
        self._create_future_production_day()

        self.stdout.write(
            self.style.SUCCESS("All pages created for tenant {}".format(tenant))
        )
