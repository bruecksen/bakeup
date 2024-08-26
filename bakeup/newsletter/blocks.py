from wagtail import blocks
from wagtail.blocks.field_block import RichTextBlock as _RichTextBlock
from wagtail.images.blocks import ImageChooserBlock

from bakeup.contrib.blocks import TextAlignmentChoiceBlock


class ImageBlock(blocks.StructBlock):
    image = ImageChooserBlock()
    caption = blocks.CharBlock(required=False)

    class Meta:  # type: ignore
        template = "blocks/image_block.html"


class RichTextBlock(blocks.StructBlock):
    alignment = TextAlignmentChoiceBlock(default="start", label="Text Alignment")
    text = _RichTextBlock(
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
        ]
    )

    class Meta:
        template = "blocks/richtext_block.html"
        label = "Text"
        icon = "pilcrow"


class StoryBlock(blocks.StreamBlock):
    rich_text = RichTextBlock()
    image = ImageBlock()
    raw_html = blocks.RawHTMLBlock()


class NewsletterSubscribeBlock(blocks.StructBlock):
    heading = blocks.CharBlock(required=False, default="Abonniere unseren Newsletter")
    text = RichTextBlock(
        default="Erhalte die neuesten Updates und Angebote direkt in dein Postfach."
    )
    button_text = blocks.CharBlock(default="Abonnieren")

    class Meta:  # type: ignore
        template = "newsletter/subscribe_block.html"


class NewsletterBlocks(blocks.StreamBlock):
    newsletter = NewsletterSubscribeBlock()
