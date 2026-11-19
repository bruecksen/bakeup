from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand
from django.db import connection
from django_tenants.management.commands import InteractiveTenantOption
from django_tenants.utils import get_public_schema_name
from wagtail.images.models import Image

from bakeup.pages.constants import BLOCK_REFERENCE_PAGE_SLUG
from bakeup.pages.models import BlockReferencePage, ShopPage

APP_DIR = Path(__file__).resolve().parent.parent.parent
FIXTURES_DIR = APP_DIR.joinpath("fixtures")


def text(html, alignment="start"):
    return {"type": "text", "value": {"text": html, "alignment": alignment}}


def intro(title, sentence):
    return text("<h2>{}</h2><p>{}</p>".format(title, sentence))


def space(size=3):
    return {"type": "space", "value": {"space": size, "space_mobile": 2}}


def without_ids(data):
    """Stream data without the ids that are generated when a page is saved."""
    if isinstance(data, dict):
        return {key: without_ids(value) for key, value in data.items() if key != "id"}
    if isinstance(data, list):
        return [without_ids(item) for item in data]
    return data


FAQ_ITEMS = [
    {
        "question": "Wann kann ich bestellen?",
        "answer": (
            "<p>Bis zum Bestellschluss des Backtags. Danach planen wir die"
            " Backstube und können keine Änderungen mehr annehmen.</p>"
        ),
    },
    {
        "question": "Wo hole ich mein Brot ab?",
        "answer": (
            "<p>An der Abholstelle, die du beim Bestellen auswählst. Eine Übersicht"
            " findest du in deinem Konto.</p>"
        ),
    },
    {
        "question": "Kann ich ein Abo abschließen?",
        "answer": (
            "<p>Ja. Lege die Brote in den Brotkorb und wähle <b>Abo</b>, dann"
            " backen wir sie an jedem Backtag für dich.</p>"
        ),
    },
]

STEPS = [
    {
        "label": "Schritt 1",
        "title": "Bestellen",
        "text": "Such dir im Shop die Brote für den nächsten Backtag aus.",
    },
    {
        "label": "Schritt 2",
        "title": "Backen",
        "text": "Wir backen alles frisch, mit Zeit und guten Zutaten.",
    },
    {
        "label": "Schritt 3",
        "title": "Abholen",
        "text": "Hol dein Brot an deiner Abholstelle ab.",
    },
]

LOREM = (
    "<p>Hier steht ein kurzer Text über eure Backstube: was euch wichtig ist,"
    " woher das Getreide kommt und warum der Teig bei euch so lange ruhen"
    " darf.</p>"
)


class Command(InteractiveTenantOption, BaseCommand):
    help = (
        "Creates or updates the block reference page (only visible to bakers) that"
        " shows every CMS block. Run it again whenever blocks change."
    )

    def _get_image(self, img_path):
        """Like `_set_image` of create_initial_demo_wagtail_pages."""
        img_path = FIXTURES_DIR.joinpath("img", img_path)
        qs = Image.objects.filter(title=img_path.name)
        if qs.exists():
            return qs[0]
        with open(img_path, "rb") as f:
            # setting name= is important. otherwise it uses the entire file path as
            # name, which leaks server filesystem structure to the outside.
            image_file = File(f, name=img_path.stem)
            image = Image(title=img_path.name, file=image_file.open())
            image.save()
        return image

    def _get_blocks(self, shop_page):
        banner = self._get_image("banner-demo.jpg").pk
        baker = self._get_image("baker.jpg").pk
        bread = self._get_image("banner.jpg").pk
        shop_link = {"target": [{"type": "page", "value": shop_page.pk}]}
        faq = {
            "type": "faq",
            "value": {"heading": "Häufige Fragen", "items": FAQ_ITEMS},
        }
        steps = {
            "type": "steps",
            "value": {"heading": "So geht's", "items": STEPS},
        }

        def image_text(position):
            return {
                "type": "image_text",
                "value": {
                    "image": baker,
                    "image_position": position,
                    "eyebrow": "Unsere Backstube",
                    "heading": "Handwerk mit Zeit",
                    "text": LOREM,
                    "buttons": [{"text": "Zum Shop", "link": shop_link}],
                },
            }

        def section(background, label, content):
            return {
                "type": "section",
                "value": {
                    "background": background,
                    "eyebrow": "Abschnitt",
                    "heading": "Hintergrund: {}".format(label),
                    "content": content,
                },
            }

        button = {"type": "button", "value": {"text": "Zum Shop", "link": shop_link}}
        newsletter = {
            "type": "newsletter",
            "value": {
                "heading": "Abonniere unseren Newsletter",
                "text": {
                    "text": "<p>Neuigkeiten aus der Backstube.</p>",
                    "alignment": "start",
                },
                "button_text": "Abonnieren",
            },
        }
        faq_in_column = {
            "type": "column12",
            "value": {
                "left": [text("<h2>Häufige Fragen</h2>")],
                "right": [
                    {"type": "faq", "value": {"heading": "", "items": FAQ_ITEMS}}
                ],
            },
        }
        three_columns = {
            "type": "column111",
            "value": {
                "left": [text("<h3>Zutaten</h3>" + LOREM)],
                "middle": [text("<h3>Handwerk</h3>" + LOREM)],
                "right": [text("<h3>Region</h3>" + LOREM)],
            },
        }

        return [
            text(
                "<h1>Baustein-Übersicht</h1><p>Diese Seite zeigt alle Bausteine, aus"
                " denen ihr eure Seiten zusammensetzen könnt. Nur ihr als"
                " Bäcker:innen seht sie. Öffnet sie im Editor, um zu sehen, wie jeder"
                " Baustein eingestellt ist.</p>"
            ),
            space(),
            intro(
                "FAQ",
                "Für häufige Fragen: Nur die Fragen sind zu sehen, die Antwort"
                " öffnet sich mit „+“.",
            ),
            faq,
            intro(
                "FAQ in einer Spalte (1|2)",
                "Überschrift links, Fragen rechts: das FAQ ohne eigene Überschrift"
                " in die rechte Spalte, einen Text in die linke.",
            ),
            faq_in_column,
            space(),
            intro(
                "Bild und Text",
                "Ein großes Foto neben einem kurzen Text, das Bild links oder rechts.",
            ),
            image_text("left"),
            image_text("right"),
            space(),
            intro(
                "Schritte",
                "Für einen kurzen Ablauf in zwei bis vier Schritten, zum Beispiel"
                " wie Bestellen und Abholen funktioniert.",
            ),
            steps,
            space(),
            intro(
                "Abschnitt",
                "Ein farbiges Band über die ganze Breite, um eine Seite zu gliedern."
                " Darin können alle anderen Bausteine stehen.",
            ),
            section("transparent", "Keiner", [text(LOREM, alignment="center"), button]),
            section("white", "Weiß", [steps]),
            section("light", "Hell", [image_text("left")]),
            section("dark", "Dunkel", [faq_in_column]),
            section("primary", "Primärfarbe", [newsletter]),
            section("secondary", "Sekundärfarbe", [three_columns]),
            space(),
            intro("Text", "Für Fließtext mit Überschriften, Listen und Links."),
            text(LOREM + LOREM),
            text(LOREM, alignment="center"),
            intro("Bild", "Ein einzelnes Bild, links, mittig oder rechts."),
            {
                "type": "image",
                "value": {
                    "image": bread,
                    "max_width": None,
                    "alignment": "center",
                    "link": {"target": []},
                },
            },
            intro("Button", "Ein Link als Button, zum Beispiel zum Shop."),
            button,
            intro("Karte", "Ein Text auf einer farbigen Fläche."),
            {
                "type": "card",
                "value": {
                    "background": "white",
                    "text": {"text": LOREM, "alignment": "start"},
                },
            },
            intro("Bilder-Karussell", "Mehrere Bilder zum Durchblättern."),
            {
                "type": "carousel",
                "value": {
                    "items": [
                        {"image": banner, "caption": "<p>Frisch gebacken</p>"},
                        {"image": bread, "caption": "<p>Aus dem Holzofen</p>"},
                    ]
                },
            },
            intro("Video", "Ein eingebettetes Video, zum Beispiel von YouTube."),
            {"type": "video", "value": "https://youtu.be/cUdZebtbd0o"},
            intro(
                "Abstand und Linie",
                "Ein Abstand oder eine Trennlinie zwischen zwei Bausteinen.",
            ),
            space(4),
            {"type": "hr", "value": {}},
            intro("Spalten", "Zwei oder drei Spalten nebeneinander."),
            {
                "type": "column11",
                "value": {"left": [text(LOREM)], "right": [text(LOREM)]},
            },
            {
                "type": "column111",
                "value": {
                    "left": [text(LOREM)],
                    "middle": [text(LOREM)],
                    "right": [text(LOREM)],
                },
            },
            {
                "type": "column21",
                "value": {
                    "left": [text(LOREM + LOREM)],
                    "right": [
                        {
                            "type": "image",
                            "value": {
                                "image": baker,
                                "max_width": None,
                                "alignment": "center",
                                "link": {"target": []},
                            },
                        }
                    ],
                },
            },
            intro(
                "HTML",
                "Für eigenes HTML, zum Beispiel ein Formular eines anderen Anbieters.",
            ),
            {
                "type": "html",
                "value": "<p><em>Hier steht eigenes HTML.</em></p>",
            },
            intro("Newsletter", "Ein Formular zum Anmelden für den Newsletter."),
            newsletter,
            intro(
                "Backtage",
                "Die nächsten geplanten Backtage, mit Link zum Bestellen.",
            ),
            {"type": "production_days", "value": {"production_day_limit": 2}},
            intro("Sortiment", "Alle Produkte, nach Kategorien geordnet."),
            {"type": "product_assortment", "value": {"only_planned_products": False}},
            intro(
                "Abholstellen",
                "Alle Abholstellen mit Adresse, Abholzeiten und Beschreibung. Die"
                " Karte zeigt die Abholstellen, für die ein Pin gesetzt ist. Der"
                " Baustein kann Karte und Liste, nur die Karte oder nur die Liste"
                " zeigen.",
            ),
            {
                "type": "points_of_sale",
                "value": {
                    "heading": "Hier gibt es unser Brot",
                    "display": "map_and_list",
                },
            },
            text("<h3>In Spalten: Text neben der Karte</h3>"),
            {
                "type": "column12",
                "value": {
                    "left": [
                        text(
                            "<h4>So findest du uns</h4><p>Der Baustein passt auch"
                            " in Spalten und Abschnitte, hier zeigt er nur die"
                            " Karte.</p>"
                        )
                    ],
                    "right": [
                        {
                            "type": "points_of_sale",
                            "value": {"heading": "", "display": "map"},
                        }
                    ],
                },
            },
        ]

    def handle(self, *args, **options):
        # Called through all_tenants_command the connection is already set.
        if options.get("schema_name") or (
            connection.schema_name == get_public_schema_name()
        ):
            tenant = self.get_tenant_from_options_or_interactive(**options)
            connection.set_tenant(tenant)
        else:
            tenant = connection.tenant

        shop_page = ShopPage.objects.first()
        if shop_page is None:
            self.stderr.write("No shop page for tenant {}, skipped.".format(tenant))
            return

        blocks = self._get_blocks(shop_page)
        page = BlockReferencePage.objects.first()
        if page is None:
            page = BlockReferencePage(
                title="Baustein-Übersicht",
                slug=BLOCK_REFERENCE_PAGE_SLUG,
                show_in_menus=False,
                content=blocks,
            )
            shop_page.add_child(instance=page)
        else:
            # The command runs on every deploy: without a change in the blocks
            # the page keeps its revision.
            field = page._meta.get_field("content")
            new_content = field.to_python(blocks)
            if without_ids(new_content.get_prep_value()) == without_ids(
                page.content.get_prep_value()
            ):
                self.stdout.write(
                    "Block reference page unchanged for tenant {}".format(tenant)
                )
                return
            page.content = blocks
        page.save_revision().publish()

        self.stdout.write(
            self.style.SUCCESS(
                "Block reference page {} saved for tenant {}".format(
                    page.url_path, tenant
                )
            )
        )
