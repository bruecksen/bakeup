import uuid

from datetime import datetime
from django.utils.translation import gettext_lazy as _
from django.utils.functional import cached_property
from django.utils.safestring import mark_safe

from wagtail.blocks.field_block import (BooleanBlock, CharBlock, ChoiceBlock, PageChooserBlock,
                                             RawHTMLBlock, RichTextBlock as _RichTextBlock, URLBlock, IntegerBlock, Block)
from wagtail.blocks.list_block import ListBlock
from wagtail.blocks.stream_block import StreamBlock
from wagtail.blocks.struct_block import StructBlock
from wagtail.blocks import StructValue
from wagtail.embeds.blocks import EmbedBlock as _EmbedBlock
from wagtail.images.blocks import ImageChooserBlock as _ImageChooserBlock
from wagtail.documents.blocks import DocumentChooserBlock
from wagtail.snippets.blocks import SnippetChooserBlock

from bakeup.shop.models import ProductionDay, Product


class EmbedBlock(_EmbedBlock):
    class Meta:
        template = 'blocks/embed_block.html'


class TextAlignmentChoiceBlock(ChoiceBlock):
    choices = [
        ('start', 'Left'), 
        ('center', 'Centre'), 
        ('end', 'Right'),
        ('justify', 'Justified'), 
    ]


class ImageAlignmentChoiceBlock(ChoiceBlock):
    choices = [
        ('start', 'Left'), 
        ('center', 'Centre'), 
        ('end', 'Right'),
    ]


class RichTextBlock(StructBlock):
    alignment = TextAlignmentChoiceBlock(
        default = 'start',
        label = "Text Alignment"
    )
    text = _RichTextBlock()

    class Meta:
        template = 'blocks/richtext_block.html'
        label = "Text"
        icon = 'pilcrow'


class ColourThemeChoiceBlock(ChoiceBlock):
    choices = [
        ('primary', 'Primary'),
        ('secondary', 'Secondary'),
        ('success', 'Green'),
        ('danger', 'Red'),
        ('warning', 'Yellow'),
        ('info', 'Blue'),
        ('light', 'Light'),
        ('dark', 'Dark'),
    ]


class ImageChooserBlock(StructBlock):
    alignment = ImageAlignmentChoiceBlock(default='start')
    image = _ImageChooserBlock()

    class Meta:
        template = 'blocks/image_block.html'
        label = "Image"
        icon = 'image'

    def get_context(self, value, parent_context=None):
        context = super().get_context(value, parent_context)
        if value.get('alignment') == 'center':
            context.update({
                'classes': 'img-fluid mx-auto d-block',
            })
        else:
            context.update({
                'classes': 'img-fluid float-{}'.format(value),
            })
        return context


class SpacerBlock(StructBlock):
    space = ChoiceBlock(choices=[(0, '0'), (1, '16px'), (2, '32px'), (3, '48px'), (4, '64px')], default=1)
    space_mobile = ChoiceBlock(choices=[(0, '0'), (1, '16px'), (2, '32px'), (3, '48px'),  (4, '64px')], default=0)

    class Meta:
        icon = "fa-arrows-v"
        template = "blocks/spacer_block.html"


class SimpleCard(StructBlock):
    background = ColourThemeChoiceBlock(
        default='bg-transparent',
        label="Card Background Colour"
    )    
    text = RichTextBlock(
        label="Card Body Text",
        help_text="Body text for this card.",
    )

    class Meta:
        template = 'blocks/simple_card_block.html'
        label = "Simple Card (Text Only)"
        icon = 'form'

class LinkTargetBlock(StreamBlock):
    """
    The target of a link, used by `LinkBlock`.
    """

    page = PageChooserBlock(
        label=_("Page"), icon='doc-empty-inverse'
    )
    document = DocumentChooserBlock(label=_("Document"), icon='doc-full')
    image = ImageChooserBlock(label=_("Image"))
    url = URLBlock(label=_("External link"))
    anchor = CharBlock(
        label=_("Anchor link"),
        help_text=mark_safe(
            _(
                "An anchor in the current page, for example: "
                "<code>#target-id</code>."
            )
        ),
    )

    def set_name(self, name):
        # Do not generate a label from the name as Block.set_name does
        self.name = name

    class Meta:
        icon = 'link'
        max_num = 1
        form_classname = 'link-target-block'


class LinkValue(StructValue):
    @cached_property
    def href(self):
        """Return the URL of the chosen target or `None` if it is undefined."""
        try:
            child_value = self['target'][0].value
        except (IndexError, KeyError):
            return None
        if hasattr(child_value, 'file') and hasattr(child_value.file, 'url'):
            href = child_value.file.url
        elif hasattr(child_value, 'url'):
            href = child_value.url
        else:
            href = child_value
        return href


class LinkBlock(StructBlock):
    """
    A link with a target chosen from a range of types - i.e. a page, an URL.
    """

    class Meta:
        icon = 'link'
        label = _("Link")
        value_class = LinkValue
        form_classname = 'link-block'
        form_template = 'pages/block_forms/link_block.html'

    def __init__(self, *args, required=True, **kwargs):
        super().__init__(*args, required=required, **kwargs)

        target = LinkTargetBlock(required=required)
        target.set_name('target')

        self.child_blocks['target'] = target

    @property
    def required(self):
        return self.meta.required


class ButtonBlock(StructBlock):
    """
    A button which acts like a link.
    """

    text = CharBlock(label=_("Text"))
    link = LinkBlock()

    class Meta:
        icon = 'link'
        label = _("Button")
        template = 'blocks/button_block.html'


class HorizontalRuleBlock(StructBlock):
    class Meta:
        icon = 'horizontalrule'
        label = _("Horizontal Rule")
        template = 'blocks/hr_block.html'


class CarouselItemBlock(StructBlock):
    image = _ImageChooserBlock()
    caption = _RichTextBlock()


class CarouselBlock(StructBlock):
    items = ListBlock(CarouselItemBlock())

    class Meta:
        icon = 'image'
        label = _('Image carousel')
        template = 'blocks/carousel_block.html'

    
    def get_context(self, value, parent_context=None):
        context = super().get_context(value, parent_context)
        context['uuid'] = uuid.uuid4()
        return context

    




class CommonBlocks(StreamBlock):
    # heading = HeadingBlock(group="Common")
    text = RichTextBlock(group="Common")
    # text_collapse = TextCollapse(group="Common")
    image = ImageChooserBlock(group="Common")
    button = ButtonBlock(group="Common")
    # round_image = RoundImageChooserBlock(group="Common")
    video = EmbedBlock(group="Common")
    html = RawHTMLBlock(group="Common")
    space = SpacerBlock(group="Common")
    card = SimpleCard(group="Common")
    hr = HorizontalRuleBlock(group="Common")
    carousel = CarouselBlock(group="Common")
    # accordion = AccordionBlock(child_block=AccordionElement(), group="Common")
    # tile = TileBlock(group="Common")

class BaseColumnTwo(StructBlock):
    left = CommonBlocks(required=False)
    right = CommonBlocks(required=False)

    class Meta:
        icon = "table"


class Column11(BaseColumnTwo):

    class Meta:
        template = 'blocks/column11_block.html'
        label = "Column (1|1)"


class Column21(BaseColumnTwo):

    class Meta:
        template = 'blocks/column21_block.html'
        label = "Column (2|1)"


class Column12(BaseColumnTwo):

    class Meta:
        template = 'blocks/column12_block.html'
        label = "Column (1|2)"


class Column111(StructBlock):
    left = CommonBlocks(required=False)
    middle = CommonBlocks(required=False)
    right = CommonBlocks(required=False)

    class Meta:
        template = 'blocks/column111_block.html'
        icon = "table"
        label = "Column (1|1|1)"


class ColumnBlocks(StreamBlock):
    column11 = Column11(group="Columns")
    column111 = Column111(group="Columns")
    column12 = Column12(group="Columns")
    column21 = Column21(group="Columns")


class ProductionDaysBlock(StructBlock):
    production_day_limit = IntegerBlock(default=4, required=False)

    class Meta:
        template = 'blocks/production_days_block.html'
        label = _('Production Days')
        icon = 'date'

    def get_context(self, value, parent_context=None):
        context = super().get_context(value, parent_context)
        production_days = ProductionDay.objects.published().upcoming()
        if parent_context and 'production_day_next' in parent_context:
            production_days = production_days.exclude(id=parent_context['production_day_next'].pk)
        if value.get('production_day_limit'):
            production_days = production_days[:value.get('production_day_limit')]
        context['production_days'] = production_days
        return context
    

class ProductAssortmentBlock(StructBlock):
    only_planned_products = BooleanBlock(default=True, required=False)

    class Meta:
        template = 'blocks/product_assortment_block.html'
        label = _('Product Assortment')
        icon = 'list-ul'

    def get_context(self, value, parent_context=None):
        context = super().get_context(value, parent_context)
        products = Product.objects.filter(is_sellable=True)
        if value.get('only_planned_products'):
            today = datetime.now().date()
            products = products.filter(production_days__production_day__day_of_sale__gte=today)
        context['products'] = products.distinct().order_by('category')
        return context


class BakeupBlocks(StreamBlock):
    production_days = ProductionDaysBlock(group="Bakeup")
    product_assortment = ProductAssortmentBlock(group="Bakeup")


class ContentBlocks(CommonBlocks, ColumnBlocks):
    pass

class AllBlocks(BakeupBlocks, CommonBlocks, ColumnBlocks):
    pass