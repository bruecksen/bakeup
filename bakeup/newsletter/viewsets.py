from django import forms
from django.urls import reverse
from django.utils.functional import cached_property
from djangoql.serializers import DjangoQLSchemaSerializer
from wagtail.admin.panels import FieldPanel
from wagtail.admin.ui.tables import Column
from wagtail.admin.views import generic
from wagtail.admin.views.generic.chooser import ChooseView
from wagtail.admin.viewsets.chooser import ChooserViewSet
from wagtail.admin.viewsets.model import ModelViewSet, ModelViewSetGroup
from wagtail.admin.widgets.button import Button

from .models import (
    Audience,
    Contact,
    ContactSchema,
    NewsletterPermissionPolicy,
    NewsletterRecipients,
    Segment,
)
from .panels import DjangoQLPanel, MembersPanel
from .widgets import DjangoQLWidget


class AudienceChooseView(ChooseView):
    @property
    def columns(self):  # type: ignore
        return super().columns + [
            Column("member_count", label="Members", accessor="member_count"),
        ]


class AudienceChooserViewSet(ChooserViewSet):
    model = Audience
    icon = "group"
    choose_one_text = "Choose an audience"
    choose_another_text = "Choose another audience"
    form_fields = ["name"]
    list_filter = ["name"]
    choose_view_class = AudienceChooseView


audience_chooser_viewset = AudienceChooserViewSet("audiencemodel_chooser")


class AudienceViewSet(ModelViewSet):
    model = Audience
    icon = "group"
    list_display = ["name", "member_count"]
    permission_policy = NewsletterPermissionPolicy(Audience)

    form_fields = [
        "name",
    ]

    panels = [
        FieldPanel("name"),
        FieldPanel("is_default"),
        MembersPanel(heading="Members"),
    ]


audience_viewset = AudienceViewSet("audiencemodel")


class SegmentViewSet(ModelViewSet):
    model = Segment
    icon = "group"
    list_display = ["name", "audience", "member_count"]
    list_filter = ["audience"]
    search_fields = ["name"]
    template_prefix = "wagtail_newsletter_simple_smtp/audience_segment/"
    permission_policy = NewsletterPermissionPolicy(Segment)
    form_fields = ["name", "audience"]

    panels = [
        FieldPanel("name"),
        FieldPanel("audience"),
        DjangoQLPanel(
            "filter_query",
            widget=DjangoQLWidget(
                introspections=DjangoQLSchemaSerializer().serialize(
                    ContactSchema(Contact)
                )
            ),
        ),
        MembersPanel("Members"),
    ]


segment_viewset = SegmentViewSet("segment")


class AudienceSegmentChooserViewSet(ChooserViewSet):
    model = Segment
    icon = "group"
    choose_one_text = "Choose an segment"
    choose_another_text = "Choose another segment"
    url_filter_parameters = ["audience"]
    preserve_url_parameters = ["multiple", "audience"]
    choose_view_class = AudienceChooseView


audience_segment_chooser_viewset = AudienceSegmentChooserViewSet(
    "audience_segment_chooser"
)


class ContactIndexView(generic.IndexView):
    @cached_property
    def header_more_buttons(self) -> list[Button]:
        buttons = super().header_more_buttons.copy()
        buttons.append(
            Button(
                "Import contacts",
                url=reverse("newsletter:start_import"),
                icon_name="doc-full-inverse",
                priority=50,
            )
        )
        return buttons


class ContactViewSet(ModelViewSet):
    model = Contact
    icon = "user"
    list_display = ["email", "first_name", "last_name", "is_active"]
    search_fields = ["email", "first_name", "last_name"]
    list_filter = ["audiences", "is_active"]
    permission_policy = NewsletterPermissionPolicy(Contact)

    form_fields = [
        "email",
        "audiences",
        "segments",
        "user",
        "is_active",
    ]

    panels = [
        FieldPanel("email"),
        FieldPanel("first_name"),
        FieldPanel("last_name"),
        FieldPanel("audiences", widget=forms.CheckboxSelectMultiple),
        FieldPanel("user"),
        FieldPanel("is_active"),
    ]

    index_view_class = ContactIndexView


contact_viewset = ContactViewSet("contact")


class NewsletterRecipientsViewSet(ModelViewSet):
    model = NewsletterRecipients
    icon = "group"
    list_display = ["name", "audience", "segment", "member_count"]
    permission_policy = NewsletterPermissionPolicy(NewsletterRecipients)

    form_fields = [
        "name",
        "audience",
        "segment",
    ]

    panels = [
        FieldPanel("name"),
        FieldPanel("audience", widget=audience_chooser_viewset.widget_class),
        FieldPanel(
            "segment",
            widget=audience_segment_chooser_viewset.widget_class(  # type: ignore
                linked_fields={"audience": "#id_audience"},
            ),
        ),
    ]


newsletter_recipients_viewset = NewsletterRecipientsViewSet("newsletter_recipients")


class RecipientsChooserViewSet(ChooserViewSet):
    model = NewsletterRecipients
    icon = "group"
    choose_one_text = "Choose recipients"
    choose_another_text = "Choose other recipients"
    choose_view_class = AudienceChooseView


recipients_chooser_viewset = RecipientsChooserViewSet("recipients_chooser")


class NewsletterViewSetGroup(ModelViewSetGroup):
    items = [
        newsletter_recipients_viewset,
        audience_viewset,
        segment_viewset,
        contact_viewset,
    ]
    menu_label = "Newsletter"
    menu_icon = "mail"


newsletter_viewset_group = NewsletterViewSetGroup()
