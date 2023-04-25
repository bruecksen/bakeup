from django.db import models

from wagtail.models import Page
from wagtail.fields import RichTextField, StreamField
from wagtail.admin.panels import FieldPanel

from bakeup.pages.blocks import AllBlocks

# Create your models here.
class ContentPage(Page):
    content = StreamField(AllBlocks(), blank=True, null=True)

    show_in_menus_default = True
    content_panels = Page.content_panels + [
        FieldPanel("content"),
    ]