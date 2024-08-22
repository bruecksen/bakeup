from wagtail.blocks.field_block import ChoiceBlock
from wagtail.blocks.field_block import RichTextBlock as _RichTextBlock
from wagtail.blocks.struct_block import StructBlock


class TextAlignmentChoiceBlock(ChoiceBlock):
    choices = [
        ("start", "Left"),
        ("center", "Centre"),
        ("end", "Right"),
        ("justify", "Justified"),
    ]


class ImageAlignmentChoiceBlock(ChoiceBlock):
    choices = [
        ("start", "Left"),
        ("center", "Centre"),
        ("end", "Right"),
    ]


class RichTextBlock(StructBlock):
    alignment = TextAlignmentChoiceBlock(default="start", label="Text Alignment")
    text = _RichTextBlock()

    class Meta:
        template = "blocks/richtext_block.html"
        label = "Text"
        icon = "pilcrow"
