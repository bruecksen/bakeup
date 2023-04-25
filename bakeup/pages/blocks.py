from wagtail.blocks.field_block import (BooleanBlock, CharBlock, ChoiceBlock, PageChooserBlock,
                                             RawHTMLBlock, RichTextBlock as _RichTextBlock, URLBlock)
from wagtail.blocks.list_block import ListBlock
from wagtail.blocks.stream_block import StreamBlock
from wagtail.blocks.struct_block import StructBlock
from wagtail.embeds.blocks import EmbedBlock as EmbedBlock
from wagtail.images.blocks import ImageChooserBlock as _ImageChooserBlock
from wagtail.snippets.blocks import SnippetChooserBlock


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


class CommonBlocks(StreamBlock):
    # heading = HeadingBlock(group="Common")
    text = RichTextBlock(group="Common")
    # text_collapse = TextCollapse(group="Common")
    image = ImageChooserBlock(group="Common")
    # round_image = RoundImageChooserBlock(group="Common")
    video = EmbedBlock(group="Common")
    html = RawHTMLBlock(group="Common")
    space = SpacerBlock(group="Common")
    card = SimpleCard(group="Common")
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



class AllBlocks(CommonBlocks, ColumnBlocks):
    pass