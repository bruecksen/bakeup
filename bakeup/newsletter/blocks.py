from django.utils.translation import gettext_lazy as _
from wagtail import blocks
from wagtail.blocks.field_block import RichTextBlock as _RichTextBlock
from wagtail.images.blocks import ImageChooserBlock

from bakeup.contrib.blocks import TextAlignmentChoiceBlock


class ImageBlock(blocks.StructBlock):
    image = ImageChooserBlock(label=_("Image"))
    caption = blocks.CharBlock(label=_("Caption"), required=False)

    class Meta:  # type: ignore
        label = _("Image")
        template = "blocks/image_block.html"


class RichTextBlock(blocks.StructBlock):
    alignment = TextAlignmentChoiceBlock(default="start", label=_("Text alignment"))
    text = _RichTextBlock(
        label=_("Text"),
        features=[
            "h1",
            "h2",
            "h3",
            "bold",
            "italic",
            "link",
            "hr",
            "ol",
            "ul",
            "blockquote",
            "code",
        ],
    )

    class Meta:
        template = "blocks/richtext_block.html"
        label = _("Text")
        icon = "pilcrow"


class StoryBlock(blocks.StreamBlock):
    rich_text = RichTextBlock()
    image = ImageBlock()
    raw_html = blocks.RawHTMLBlock(label=_("HTML"))


class NewsletterSubscribeBlock(blocks.StructBlock):
    heading = blocks.CharBlock(
        label=_("Heading"), required=False, default="Abonniere unseren Newsletter"
    )
    text = RichTextBlock(
        label=_("Text"),
        default="Erhalte die neuesten Updates und Angebote direkt in dein Postfach.",
    )
    button_text = blocks.CharBlock(label=_("Button text"), default="Abonnieren")

    class Meta:  # type: ignore
        label = _("Newsletter sign-up")
        template = "newsletter/subscribe_block.html"


class NewsletterBlocks(blocks.StreamBlock):
    newsletter = NewsletterSubscribeBlock()
