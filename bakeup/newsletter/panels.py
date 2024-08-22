import logging

from django.core.exceptions import ImproperlyConfigured
from django.utils.functional import cached_property
from djangoql.serializers import DjangoQLSchemaSerializer
from wagtail.admin.panels import FieldPanel, Panel

from . import forms, get_backend, models

logger = logging.getLogger(__name__)


class DjangoQLPanel(FieldPanel):
    class BoundPanel(FieldPanel.BoundPanel):
        def get_context_data(self, parent_context=None):
            context = super().get_context_data(parent_context=parent_context)
            context["introspections"] = DjangoQLSchemaSerializer().serialize(
                models.ContactSchema(models.Contact)
            )
            return context


class MembersPanel(Panel):
    class BoundPanel(Panel.BoundPanel):
        template_name = "newsletter/panels/contact_panel.html"

        # instance = "models.NewsletterPageMixin"

        class Media:
            js = [
                "wagtail_newsletter/js/wagtail_newsletter.js",
            ]

        def __init__(self, panel, instance, request, form, prefix):
            super().__init__(panel, instance, request, form, prefix)
            if self.instance.pk:
                if not hasattr(self.instance, "members"):
                    raise ImproperlyConfigured(
                        "The MembersPanel requires a 'members' attribute."
                    )
                self.heading = f"{self.panel.heading}: {self.instance.member_count} "

        # @cached_property
        # def permissions(self):
        #     return frozenset(
        #         action
        #         for action in [
        #             "save_campaign",
        #             "send_test_email",
        #             "send_campaign",
        #             "get_report",
        #         ]
        #         if self.instance.has_newsletter_permission(self.request.user, action)
        #     )

        def get_context_data(self, parent_context=None):
            context = super().get_context_data(parent_context) or {}

            if self.instance.pk:
                context["members"] = self.instance.members
            return context

        # def is_shown(self):  # type: ignore
        #     return bool(self.permissions)


class NewsletterPanel(Panel):
    class BoundPanel(Panel.BoundPanel):
        template_name = "newsletter/panels/newsletter_panel.html"

        instance: "models.NewsletterPageMixin"

        class Media:
            css = {"all": ["css/wagtail_newsletter.css"]}
            js = ["js/wagtail_newsletter.js"]

        @cached_property
        def permissions(self):
            return frozenset(
                action
                for action in [
                    "save_campaign",
                    "send_test_email",
                    "send_campaign",
                    "get_report",
                ]
                if self.instance.has_newsletter_permission(self.request.user, action)
            )

        def get_context_data(self, parent_context=None):
            context = super().get_context_data(parent_context) or {}
            backend = get_backend()
            campaign = self.instance

            context["backend_name"] = backend.name
            context["campaign"] = self.instance
            context["test_form"] = forms.SendTestEmailForm(
                initial={"email": self.request.user.email},
                prefix="newsletter-test",
            )

            if campaign is not None and campaign.sent:
                context["sent"] = True
                if "get_report" in self.permissions:
                    context["report"] = campaign.get_report()

            context["has_action_permission"] = {
                permission: True for permission in self.permissions
            }

            return context

        def is_shown(self):  # type: ignore
            return bool(self.permissions)
