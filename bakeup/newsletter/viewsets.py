from djangoql.serializers import DjangoQLSchemaSerializer
from wagtail.admin.panels import FieldPanel
from wagtail_newsletter_simple_smtp.viewsets import SegmentViewSet as _SegmentViewSet

from .models import Contact, ContactSchema, Segment
from .panels import DjangoQLPanel


class SegmentEditView(_SegmentViewSet.edit_view_class):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Edit segment"
        context["introspections"] = DjangoQLSchemaSerializer().serialize(
            ContactSchema(Contact)
        )
        return context


class SegmentViewSet(_SegmentViewSet):
    model = Segment
    edit_view_class = SegmentEditView

    panels = [
        FieldPanel("name"),
        FieldPanel("audience"),
        DjangoQLPanel("filter_query"),
    ]


segment_viewset = SegmentViewSet("segment")
