import uuid

from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from wagtail.blocks import StructValue
from wagtail.blocks.field_block import (
    BooleanBlock,
    CharBlock,
    ChoiceBlock,
    IntegerBlock,
    PageChooserBlock,
    RawHTMLBlock,
    TextBlock,
    URLBlock,
)
from wagtail.blocks.field_block import RichTextBlock as _RichTextBlock
from wagtail.blocks.list_block import ListBlock
from wagtail.blocks.stream_block import StreamBlock
from wagtail.blocks.struct_block import StructBlock
from wagtail.documents.blocks import DocumentChooserBlock
from wagtail.embeds.blocks import EmbedBlock as _EmbedBlock
from wagtail.images.blocks import ImageChooserBlock as _ImageChooserBlock

from bakeup.contrib.blocks import ImageAlignmentChoiceBlock, RichTextBlock
from bakeup.newsletter.blocks import NewsletterSubscribeBlock
from bakeup.pages.constants import POINTS_OF_SALE_DISPLAY_CHOICES
from bakeup.shop.maps import get_point_of_sale_overview_context
from bakeup.shop.models import Product, ProductionDay
from bakeup.workshop.models import prefetch_product_cards


class EmbedBlock(_EmbedBlock):
    class Meta:
        label = _("Video")
        template = "blocks/embed_block.html"


class ColourThemeChoiceBlock(ChoiceBlock):
    choices = [
        ("primary", _("Primary")),
        ("secondary", _("Secondary")),
        ("success", _("Green")),
        ("danger", _("Red")),
        ("warning", _("Yellow")),
        ("info", _("Blue")),
        ("light", _("Light")),
        ("dark", _("Dark")),
        ("white", _("White")),
    ]


class SpacerBlock(StructBlock):
    space = ChoiceBlock(
        choices=[(0, "0"), (1, "16px"), (2, "32px"), (3, "48px"), (4, "64px")],
        default=1,
        label=_("Space"),
    )
    space_mobile = ChoiceBlock(
        choices=[(0, "0"), (1, "16px"), (2, "32px"), (3, "48px"), (4, "64px")],
        default=0,
        label=_("Space on mobile"),
    )

    class Meta:
        icon = "spacer"
        label = _("Space")
        template = "blocks/spacer_block.html"


class SimpleCard(StructBlock):
    background = ColourThemeChoiceBlock(
        default="bg-transparent", label=_("Card background colour")
    )
    text = RichTextBlock(
        label=_("Card text"),
        help_text=_("Body text for this card."),
    )

    class Meta:
        template = "blocks/simple_card_block.html"
        label = _("Simple card (text only)")
        icon = "form"


class LinkTargetBlock(StreamBlock):
    """
    The target of a link, used by `LinkBlock`.
    """

    page = PageChooserBlock(label=_("Page"), icon="doc-empty-inverse")
    document = DocumentChooserBlock(label=_("Document"), icon="doc-full")
    link = CharBlock(label=_("Internal link"))
    url = URLBlock(label=_("External link"))
    anchor = CharBlock(
        label=_("Anchor link"),
        help_text=mark_safe(
            _("An anchor in the current page, for example: <code>#target-id</code>.")
        ),
    )

    def set_name(self, name):
        # Do not generate a label from the name as Block.set_name does
        self.name = name

    class Meta:
        icon = "link"
        max_num = 1
        form_classname = "link-target-block"


class LinkValue(StructValue):
    def href(self):
        """Return the URL of the chosen target or `None` if it is undefined."""
        try:
            child_value = self["target"][0].value
        except (IndexError, KeyError):
            return None
        if hasattr(child_value, "file") and hasattr(child_value.file, "url"):
            href = child_value.file.url
        elif hasattr(child_value, "link"):
            href = child_value.link
        elif hasattr(child_value, "url"):
            href = child_value.url
        else:
            href = child_value
        return href


class LinkBlock(StructBlock):
    """
    A link with a target chosen from a range of types - i.e. a page, an URL.
    """

    class Meta:
        icon = "link"
        label = _("Link")
        value_class = LinkValue
        form_classname = "link-block"
        form_template = "pages/block_forms/link_block.html"

    def __init__(self, *args, required=True, **kwargs):
        super().__init__(*args, required=required, **kwargs)

        target = LinkTargetBlock(required=required)
        target.set_name("target")

        self.child_blocks["target"] = target

    @property
    def required(self):
        return self.meta.required


class ImageChooserBlock(StructBlock):
    image = _ImageChooserBlock(label=_("Image"))
    max_width = IntegerBlock(
        label=_("Maximum width"),
        required=False,
        help_text=_("Set a maximum width for the image in pixels."),
        min_value=0,
    )
    alignment = ImageAlignmentChoiceBlock(default="start", label=_("Alignment"))
    link = LinkBlock(required=False)

    class Meta:
        template = "blocks/image_block.html"
        label = _("Image")
        icon = "image"

    def get_context(self, value, parent_context=None):
        context = super().get_context(value, parent_context)
        if value.get("alignment") == "center":
            context.update(
                {
                    "classes": "img-fluid mx-auto d-block",
                }
            )
        else:
            context.update(
                {
                    "classes": "img-fluid float-{}".format(value.get("alignment")),
                }
            )
        if value.get("max_width"):
            context["max_width"] = "max-width: {}px;".format(value.get("max_width"))
        return context


class ButtonBlock(StructBlock):
    """
    A button which acts like a link.
    """

    text = CharBlock(label=_("Text"))
    link = LinkBlock()

    class Meta:
        icon = "link"
        label = _("Button")
        template = "blocks/button_block.html"


class HorizontalRuleBlock(StructBlock):
    class Meta:
        icon = "line"
        label = _("Line")
        template = "blocks/hr_block.html"


class CarouselItemBlock(StructBlock):
    image = _ImageChooserBlock(label=_("Image"))
    caption = _RichTextBlock(label=_("Caption"))


class CarouselBlock(StructBlock):
    items = ListBlock(CarouselItemBlock(), label=_("Images"))

    class Meta:
        icon = "image"
        label = _("Image carousel")
        template = "blocks/carousel_block.html"

    def get_context(self, value, parent_context=None):
        context = super().get_context(value, parent_context)
        context["uuid"] = uuid.uuid4()
        return context


class FaqItemBlock(StructBlock):
    question = CharBlock(label=_("Question"))
    answer = _RichTextBlock(
        label=_("Answer"), features=["bold", "italic", "link", "ol", "ul"]
    )


class FaqBlock(StructBlock):
    """
    Questions only, each answer opens when the question is clicked.
    """

    heading = CharBlock(label=_("Heading"), required=False)
    items = ListBlock(FaqItemBlock(), label=_("Questions"))

    class Meta:
        icon = "help"
        label = _("FAQ")
        template = "blocks/faq_block.html"

    def get_context(self, value, parent_context=None):
        context = super().get_context(value, parent_context)
        context["uuid"] = uuid.uuid4()
        return context


class ImageTextBlock(StructBlock):
    image = _ImageChooserBlock(label=_("Image"))
    image_position = ChoiceBlock(
        choices=[("left", _("Left")), ("right", _("Right"))],
        default="left",
        label=_("Image position"),
    )
    eyebrow = CharBlock(
        label=_("Eyebrow"),
        required=False,
        help_text=_("A short line above the heading, for example: Our bakery."),
    )
    heading = CharBlock(label=_("Heading"), required=False)
    text = _RichTextBlock(label=_("Text"))
    buttons = ListBlock(ButtonBlock(), label=_("Buttons"), default=[])

    class Meta:
        icon = "image"
        label = _("Image and text")
        template = "blocks/image_text_block.html"


class StepItemBlock(StructBlock):
    label = CharBlock(
        label=_("Label"),
        required=False,
        help_text=_("A short line above the title, for example: Step 1."),
    )
    title = CharBlock(label=_("Title"))
    text = TextBlock(label=_("Text"), required=False)


class StepsBlock(StructBlock):
    heading = CharBlock(label=_("Heading"), required=False)
    items = ListBlock(StepItemBlock(), label=_("Steps"))

    class Meta:
        icon = "list-ol"
        label = _("Steps")
        template = "blocks/steps_block.html"

    def get_context(self, value, parent_context=None):
        context = super().get_context(value, parent_context)
        # One row on large screens for up to four steps, more steps wrap.
        context["columns"] = min(max(len(value["items"]), 1), 4)
        return context


class PointsOfSaleBlock(StructBlock):
    """
    All public points of sale with address, opening hours and description,
    and a map of those that have a pin.
    """

    heading = CharBlock(label=_("Heading"), required=False)
    display = ChoiceBlock(
        choices=POINTS_OF_SALE_DISPLAY_CHOICES,
        default="map_and_list",
        label=_("Display"),
    )

    class Meta:
        template = "blocks/points_of_sale_block.html"
        label = _("Points of sale")
        icon = "site"

    def get_context(self, value, parent_context=None):
        context = super().get_context(value, parent_context)
        context.update(
            get_point_of_sale_overview_context(
                show_map=value.get("display") != "list",
                show_list=value.get("display") != "map",
            )
        )
        return context


class CommonBlocks(StreamBlock):
    # heading = HeadingBlock(group=_("Common"))
    text = RichTextBlock(group=_("Common"))
    # text_collapse = TextCollapse(group=_("Common"))
    image = ImageChooserBlock(group=_("Common"))
    button = ButtonBlock(group=_("Common"))
    # round_image = RoundImageChooserBlock(group=_("Common"))
    video = EmbedBlock(group=_("Common"))
    html = RawHTMLBlock(group=_("Common"), label=_("HTML"))
    space = SpacerBlock(group=_("Common"))
    card = SimpleCard(group=_("Common"))
    hr = HorizontalRuleBlock(group=_("Common"))
    carousel = CarouselBlock(group=_("Common"))
    newsletter = NewsletterSubscribeBlock(group=_("Common"))
    faq = FaqBlock(group=_("Common"))
    image_text = ImageTextBlock(group=_("Common"))
    steps = StepsBlock(group=_("Common"))
    # In the common blocks, so that it also fits into sections and columns.
    points_of_sale = PointsOfSaleBlock(group=_("Bakeup"))
    # tile = TileBlock(group=_("Common"))


class BaseColumnTwo(StructBlock):
    left = CommonBlocks(required=False, label=_("Left"))
    right = CommonBlocks(required=False, label=_("Right"))

    class Meta:
        icon = "table"


class Column11(BaseColumnTwo):
    class Meta:
        template = "blocks/column11_block.html"
        label = _("Columns (1|1)")


class Column21(BaseColumnTwo):
    class Meta:
        template = "blocks/column21_block.html"
        label = _("Columns (2|1)")


class Column12(BaseColumnTwo):
    class Meta:
        template = "blocks/column12_block.html"
        label = _("Columns (1|2)")


class Column111(StructBlock):
    left = CommonBlocks(required=False, label=_("Left"))
    middle = CommonBlocks(required=False, label=_("Middle"))
    right = CommonBlocks(required=False, label=_("Right"))

    class Meta:
        template = "blocks/column111_block.html"
        icon = "table"
        label = _("Columns (1|1|1)")


class ColumnBlocks(StreamBlock):
    column11 = Column11(group=_("Columns"))
    column111 = Column111(group=_("Columns"))
    column12 = Column12(group=_("Columns"))
    column21 = Column21(group=_("Columns"))


class ProductionDaysBlock(StructBlock):
    production_day_limit = IntegerBlock(
        default=4, required=False, label=_("Maximum number of production days")
    )
    text_no_production_day = RichTextBlock(
        required=False,
        label=_("Text without production days"),
        help_text=_("This text is displayed if no production day is planned."),
    )
    cta_button_text = CharBlock(
        default="Zum Backtag", required=False, label=_("Button text")
    )

    class Meta:
        template = "blocks/production_days_block.html"
        label = _("Production Days")
        icon = "date"

    def get_context(self, value, parent_context=None):
        context = super().get_context(value, parent_context)
        if parent_context and "request" in parent_context:
            production_days = (
                ProductionDay.objects.published()
                .upcoming()
                .available_to_user(parent_context["request"].user)
            )
        else:
            production_days = ProductionDay.objects.published().upcoming().available()
        if parent_context and "production_day" in parent_context:
            production_days = production_days.exclude(
                id=parent_context["production_day"].pk
            )
        if value.get("production_day_limit"):
            production_days = production_days[: value.get("production_day_limit")]
        context["production_days"] = production_days
        return context


class ProductAssortmentBlock(StructBlock):
    only_planned_products = BooleanBlock(
        default=True, required=False, label=_("Only planned products")
    )

    class Meta:
        template = "blocks/product_assortment_block.html"
        label = _("Assortment")
        icon = "list-ul"

    def get_context(self, value, parent_context=None):
        context = super().get_context(value, parent_context)
        products = Product.objects.filter(is_sellable=True)
        if value.get("only_planned_products"):
            products = products.filter(
                production_days__production_day__day_of_sale__gte=timezone.localdate()
            )
        products = prefetch_product_cards(
            list(
                products.select_related("category")
                .distinct()
                .order_by("category__name", "name")
            )
        )
        # One entry per category, products without a category come last.
        categories = {}
        for product in products:
            category = categories.setdefault(
                product.category_id,
                {
                    "key": product.category_id or "other",
                    "name": product.category.name if product.category else _("Other"),
                    "products": [],
                },
            )
            category["products"].append(product)
        other = categories.pop(None, None)
        context["categories"] = list(categories.values()) + ([other] if other else [])
        # A single category has nothing to choose from, so it is shown open.
        context["expanded"] = len(context["categories"]) == 1
        # Several assortments on one page need different collapse ids.
        context["uuid"] = uuid.uuid4()
        return context


class BakeupBlocks(StreamBlock):
    production_days = ProductionDaysBlock(group=_("Bakeup"))
    product_assortment = ProductAssortmentBlock(group=_("Bakeup"))


class ContentBlocks(CommonBlocks, ColumnBlocks):
    pass


class SectionBackgroundChoiceBlock(ChoiceBlock):
    choices = [
        ("transparent", _("None")),
        ("white", _("White")),
        ("light", _("Light")),
        ("dark", _("Dark")),
        ("primary", _("Primary")),
        ("secondary", _("Secondary")),
    ]


class SectionBlock(StructBlock):
    """
    A band across the full width of the page with its own background colour.
    """

    background = SectionBackgroundChoiceBlock(default="white", label=_("Background"))
    eyebrow = CharBlock(label=_("Eyebrow"), required=False)
    heading = CharBlock(label=_("Heading"), required=False)
    content = ContentBlocks()

    class Meta:
        icon = "placeholder"
        label = _("Section")
        template = "blocks/section_block.html"

    def get_context(self, value, parent_context=None):
        context = super().get_context(value, parent_context)
        background = value.get("background")
        if background == "transparent":
            context["background_class"] = ""
        elif background == "white":
            # Bootstrap has no text-bg-white, the text keeps the body colour.
            context["background_class"] = "bg-white"
        else:
            context["background_class"] = "text-bg-{}".format(background)
        return context


class LayoutBlocks(StreamBlock):
    section = SectionBlock(group=_("Layout"))


class AllBlocks(BakeupBlocks, CommonBlocks, ColumnBlocks, LayoutBlocks):
    pass
