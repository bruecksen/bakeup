from django.utils.translation import gettext_lazy as _
from wagtail.blocks.field_block import ChoiceBlock
from wagtail.blocks.field_block import RichTextBlock as _RichTextBlock
from wagtail.blocks.struct_block import StructBlock


class TextAlignmentChoiceBlock(ChoiceBlock):
    choices = [
        ("start", _("Left")),
        ("center", _("Centre")),
        ("end", _("Right")),
        ("justify", _("Justified")),
    ]


class ImageAlignmentChoiceBlock(ChoiceBlock):
    choices = [
        ("start", _("Left")),
        ("center", _("Centre")),
        ("end", _("Right")),
    ]


class RichTextBlock(StructBlock):
    alignment = TextAlignmentChoiceBlock(default="start", label=_("Text alignment"))
    text = _RichTextBlock(label=_("Text"))

    class Meta:
        template = "blocks/richtext_block.html"
        label = _("Text")
        icon = "pilcrow"
