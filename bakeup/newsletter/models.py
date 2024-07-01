from datetime import date

from django.db import models
from djangoql.queryset import DjangoQLQuerySet
from djangoql.schema import DjangoQLSchema
from wagtail.admin.panels import FieldPanel
from wagtail.models import Page
from wagtail.permission_policies.base import ModelPermissionPolicy
from wagtail_newsletter_simple_smtp.models import AudienceSegment as _AudienceSegment
from wagtail_newsletter_simple_smtp.models import Contact as _Contact
from wagtail_newsletter_simple_smtp.models import NewsletterPageMixin

from bakeup.core.fields import StreamField
from bakeup.users.models import User

from .blocks import StoryBlock


class NewsletterPage(NewsletterPageMixin, Page):  # type: ignore
    author = models.CharField(max_length=255, blank=True)
    date = models.DateField("Publishing date", default=date.today)
    body = StreamField(StoryBlock(), blank=True, use_json_field=True)

    content_panels = Page.content_panels + [
        FieldPanel("author"),
        FieldPanel("date"),
        FieldPanel("body"),
    ]

    newsletter_template = "newsletter/newsletter.html"

    class Meta:  # type: ignore
        permissions = [
            ("sendnewsletter_articlepage", "Can send newsletter"),
        ]

    def has_newsletter_permission(self, user, action):
        permission_policy = ModelPermissionPolicy(type(self))
        return permission_policy.user_has_permission(user, "sendnewsletter")

    @classmethod
    def get_newsletter_panels(cls):
        panels = [panel.clone() for panel in super().get_newsletter_panels()]
        for panel in panels:
            panel.permission = "demo.sendnewsletter_articlepage"
        return panels


class Segment(_AudienceSegment):
    filter_query = models.TextField(blank=True, null=True)

    @property
    def member_count(self):
        pass

    @property
    def members(self):
        pass


class Contact(_Contact):
    user = models.OneToOneField(
        "users.User", on_delete=models.CASCADE, related_name="contact"
    )

    objects = DjangoQLQuerySet.as_manager()


class ContactSchema(DjangoQLSchema):
    include = (Contact, User)


class ContactQuerySet(DjangoQLQuerySet):
    djangoql_schema = ContactSchema
