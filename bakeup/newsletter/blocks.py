from wagtail import blocks
from wagtail.images.blocks import ImageChooserBlock

from bakeup.contrib.blocks import RichTextBlock


class ImageBlock(blocks.StructBlock):
    image = ImageChooserBlock()
    caption = blocks.CharBlock(required=False)

    class Meta:  # type: ignore
        template = "blocks/image_block.html"


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
