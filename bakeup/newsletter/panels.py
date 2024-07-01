import logging

from djangoql.serializers import DjangoQLSchemaSerializer
from wagtail.admin.panels import FieldPanel

from .models import Contact, ContactSchema

logger = logging.getLogger(__name__)


class DjangoQLPanel(FieldPanel):
    class BoundPanel(FieldPanel.BoundPanel):
        def get_context_data(self, parent_context=None):
            context = super().get_context_data(parent_context=parent_context)
            context["introspections"] = DjangoQLSchemaSerializer().serialize(
                ContactSchema(Contact)
            )
            return context
