from factory import Sequence
from factory.django import DjangoModelFactory, ImageField
from wagtail.images.models import Image
from wagtail.models import Page

from bakeup.pages.models import (
    BlockReferencePage,
    ContentPage,
    PointOfSalePage,
    ShopPage,
)


class ImageFactory(DjangoModelFactory):
    title = Sequence(lambda n: f"Image {n}")
    file = ImageField(width=900, height=700)

    class Meta:
        model = Image


class PageFactory(DjangoModelFactory):
    """
    Adds the page to the tree, below `parent` or the Wagtail root page.
    """

    title = Sequence(lambda n: f"Page {n}")

    class Meta:
        abstract = True

    @classmethod
    def _create(cls, model_class, *args, parent=None, **kwargs):
        page = model_class(*args, **kwargs)
        (parent or Page.get_first_root_node()).add_child(instance=page)
        return page


class ShopPageFactory(PageFactory):
    show_production_day = False

    class Meta:
        model = ShopPage


class ContentPageFactory(PageFactory):
    class Meta:
        model = ContentPage


class BlockReferencePageFactory(PageFactory):
    class Meta:
        model = BlockReferencePage


class PointOfSalePageFactory(PageFactory):
    class Meta:
        model = PointOfSalePage
