import uuid
from datetime import date
from typing import Any, Optional
from urllib.parse import urljoin

from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import send_mail
from django.db import connection, models
from django.db.models import Exists, OuterRef, Q, UniqueConstraint
from django.http import HttpResponse, HttpResponseNotFound
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import SafeString
from django.utils.translation import gettext_lazy as _
from djangoql.exceptions import DjangoQLParserError
from djangoql.parser import DjangoQLParser
from djangoql.queryset import DjangoQLQuerySet
from djangoql.schema import BoolField, DjangoQLSchema
from modelcluster.models import ClusterableModel
from wagtail.admin.forms import WagtailAdminPageForm
from wagtail.admin.panels import FieldPanel, ObjectList, TabbedInterface
from wagtail.models import Page
from wagtail.permission_policies.base import ModelPermissionPolicy
from wagtail.search import index

from bakeup.contrib.utils import html_to_plaintext
from bakeup.core.fields import StreamField
from bakeup.newsletter.panels import NewsletterPanel
from bakeup.pages.blocks import AllBlocks
from bakeup.pages.models import BrandSettings, EmailSettings
from bakeup.shop.models import Customer, PointOfSale
from bakeup.users.models import User

from .blocks import StoryBlock


class NewsletterPermissionPolicy(ModelPermissionPolicy):
    def user_has_permission(self, user, action):
        tenant = connection.get_tenant()
        if tenant.clientsetting.is_newsletter_enabled:
            return True
        return False


class CampaignStatus(models.IntegerChoices):
    UNSENT = 0, _("unsent")
    SENDING = 1, _("sending")
    SENT = 2, _("sent")
    FAILED = 3, _("failed")
    SCHEDULED = 4, _("scheduled")


class NewsletterListPage(Page):
    parent_page_types = ["pages.ShopPage", "pages.ContentPage"]

    content = StreamField(AllBlocks(), blank=True, null=True, use_json_field=True)

    template = "newsletter/newsletter_archive.html"

    content_panels = Page.content_panels + [
        FieldPanel("content"),
    ]

    @classmethod
    def can_create_at(cls, parent):
        # Custom logic to determine if page can be created
        tenant = connection.get_tenant()
        if tenant.clientsetting.is_newsletter_enabled:
            return True
        return False

    def get_newsletter_archive(self):
        return (
            NewsletterPage.objects.live()
            .filter(web_version=True, date__lte=timezone.now())
            .descendant_of(self)
            .order_by("-date")
        )


class NewsletterPageMixin(Page):
    base_form_class: type

    newsletter_recipients = models.ForeignKey(
        "newsletter.NewsletterRecipients",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    newsletter_subject = models.CharField(
        max_length=1000,
        blank=True,
        help_text="Subject for the newsletter. Defaults to page title if blank.",
    )
    newsletter_schedule_date = models.DateTimeField(
        blank=True,
        null=True,
        help_text=(
            "Date and time when the newsletter should be sent. If blank the newsletter"
            " will be sent immediately."
        ),
    )
    web_version = models.BooleanField(
        default=False,
        help_text="If checked a web version of the newsletter will be published.",
    )

    class Meta:  # type: ignore
        abstract = True

    def serve(self, request, *args, **kwargs):
        if self.web_version:
            return super().serve(request, *args, **kwargs)
        else:
            return HttpResponseNotFound()

    @classmethod
    def can_create_at(cls, parent):
        # Custom logic to determine if page can be created
        tenant = connection.get_tenant()
        if tenant.clientsetting.is_newsletter_enabled:
            return True
        return False

    @classmethod
    def get_newsletter_panels(cls):
        from .viewsets import recipients_chooser_viewset

        return [
            FieldPanel(
                "newsletter_recipients",
                heading="Recipients",
                widget=recipients_chooser_viewset.widget_class,
            ),
            FieldPanel("newsletter_subject", heading="Subject"),
            FieldPanel("newsletter_schedule_date", heading="Schedule"),
            FieldPanel("web_version", heading="Web version"),
            NewsletterPanel(heading="Campaign"),
        ]

    preview_modes = [  # type: ignore
        ("", _("Default")),
        ("newsletter", _("Newsletter")),
    ]

    @classmethod
    def get_edit_handler(cls):  # pragma: no cover
        tabs = []

        if cls.content_panels:
            tabs.append(ObjectList(cls.content_panels, heading=_("Content")))
        if cls.promote_panels:
            tabs.append(ObjectList(cls.promote_panels, heading=_("Promote")))
        if cls.settings_panels:
            tabs.append(ObjectList(cls.settings_panels, heading=_("Settings")))

        tabs.append(ObjectList(cls.get_newsletter_panels(), heading=_("Newsletter")))

        edit_handler = TabbedInterface(tabs, base_form_class=cls.base_form_class)

        return edit_handler.bind_to_model(cls)

    def has_newsletter_permission(self, user, action):
        permission_policy = NewsletterPermissionPolicy(type(self))
        return permission_policy.user_has_permission(user, "publish")

    newsletter_template: str

    def get_newsletter_template(self) -> str:
        return self.newsletter_template

    def get_newsletter_context(self) -> "dict[str, Any]":
        return {"page": self}

    def get_newsletter_html(self) -> SafeString:
        return render_to_string(
            template_name=self.get_newsletter_template(),
            context=self.get_newsletter_context(),
        )

    def serve_preview(self, request, mode_name):  # type: ignore
        if mode_name == "newsletter":
            return HttpResponse(self.get_newsletter_html().encode())

        return super().serve_preview(request, mode_name)


class NewsletterPage(NewsletterPageMixin):  # type: ignore
    parent_page_types = ["newsletter.NewsletterListPage"]
    author = models.CharField(max_length=255, blank=True)
    date = models.DateField("Publishing date", default=date.today)
    body = StreamField(StoryBlock(), blank=True, use_json_field=True)
    status = models.IntegerField(
        verbose_name=_("status"),
        choices=CampaignStatus.choices,
        default=CampaignStatus.UNSENT,
    )
    sent_date = models.DateTimeField(blank=True, null=True)
    receipts = models.ManyToManyField(
        "newsletter.Contact",
        verbose_name=_("receipts"),
        through="newsletter.Receipt",
    )

    content_panels = Page.content_panels + [
        FieldPanel("author"),
        FieldPanel("date"),
        FieldPanel("body"),
    ]

    newsletter_template = "newsletter/newsletter.html"
    template = "newsletter/newsletter.html"

    def has_newsletter_permission(self, user, action):
        permission_policy = NewsletterPermissionPolicy(type(self))
        return permission_policy.user_has_permission(user, "sendnewsletter")

    @property
    def sent(self):
        return self.status == CampaignStatus.SENT

    @property
    def scheduled(self):
        return self.status == CampaignStatus.SCHEDULED

    @property
    def sending(self):
        return self.status == CampaignStatus.SENDING

    def get_report(self):
        return {
            "send_time": self.sent_date,
            "emails_sent": self.receipts.count(),
            "opens": 0,
            "clicks": 0,
        }

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        context["brand_settings"] = BrandSettings.load(request)
        context["email_settings"] = EmailSettings.load(request)
        return context

    def get_newsletter_context(
        self, contact, brand_settings, email_settings, absolute_url
    ) -> "dict[str, Any]":
        return {
            "page": self,
            "brand_settings": brand_settings,  # BrandSettings.load(request)
            "email_settings": email_settings,  # EmailSettings.load(request)
            "contact": contact,
            "absolute_url": absolute_url,
        }

    def get_newsletter_html(
        self, contact, brand_settings, email_settings, absolute_url
    ) -> SafeString:
        return render_to_string(
            template_name=self.get_newsletter_template(),
            context=self.get_newsletter_context(
                contact, brand_settings, email_settings, absolute_url
            ),
        )

    def serve_preview(self, request, mode_name):  # type: ignore
        if mode_name == "newsletter":
            return HttpResponse(
                self.get_newsletter_html(
                    request.user.contact,
                    BrandSettings.load(request),
                    EmailSettings.load(request),
                    request.tenant.default_full_url,
                ).encode()
            )

        return super().serve_preview(request, mode_name)


class Audience(models.Model, index.Indexed):
    name = models.CharField()
    is_default = models.BooleanField(
        default=False, help_text="Default audience for new contacts"
    )

    search_fields = [
        index.SearchField("name"),
    ]

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=("is_default",),
                condition=Q(is_default=True),
                name="one_default_audience",
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def member_count(self) -> Optional[int]:
        return self.members.count()

    @property
    def members(self):
        members = self.contacts.all()
        return members


class SegmentForm(WagtailAdminPageForm):
    def clean(self):
        cleaned_data = super().clean()
        filter_query = cleaned_data.get("filter_query")
        if filter_query:
            try:
                DjangoQLParser().parse(filter_query)
            except DjangoQLParserError as e:
                self.add_error("filter_query", e)

        return cleaned_data


class Segment(models.Model):
    filter_query = models.TextField(blank=True, null=True)
    audience = models.ForeignKey(
        "newsletter.Audience", on_delete=models.PROTECT, related_name="segments"
    )  # noqa: DJ001
    name = models.CharField()

    base_form_class = SegmentForm

    class Meta:
        verbose_name = "Segment"
        verbose_name_plural = "Segments"

    def __str__(self):
        return self.name

    @property
    def member_count(self):
        return self.members.count()

    @property
    def members(self):
        members = self.audience.contacts.all()
        if self.filter_query:
            members = members.annotate(
                is_customer=Exists(Customer.objects.filter(user=OuterRef("user")))
            )
            members = members.djangoql(self.filter_query, ContactSchema)
        return members

    def clean(self):
        # TODO: Validate filter_query
        if self.filter_query:
            pass


class NewsletterRecipients(models.Model, index.Indexed):
    name = models.CharField(max_length=1000)
    audience = models.ForeignKey(
        "newsletter.Audience", on_delete=models.PROTECT
    )  # noqa: DJ001
    segment = models.ForeignKey(
        Segment, on_delete=models.SET_NULL, blank=True, null=True
    )  # noqa: DJ001

    search_fields = [
        index.SearchField("name"),
    ]

    class Meta:  # type: ignore
        verbose_name_plural = "Newsletter recipients"

    def __str__(self):
        return self.name

    def clean(self):
        pass

    @property
    def member_count(self) -> Optional[int]:
        if self.segment:
            return self.segment.member_count
        elif self.audience:
            return self.audience.member_count
        return None

    @property
    def members(self) -> Optional[int]:
        if self.segment:
            return self.segment.members
        elif self.audience:
            return self.audience.members
        return None


class Receipt(models.Model):
    campaign = models.ForeignKey(NewsletterPage, on_delete=models.CASCADE)
    contact = models.ForeignKey("newsletter.Contact", on_delete=models.CASCADE)
    sent_date = models.DateTimeField(auto_now=True)
    # Probably not necessary, but might come in useful later
    success = models.BooleanField(default=True)


class ContactQuerySet(DjangoQLQuerySet):
    pass


class ContactManager(models.Manager):
    def contacts(self):
        contacts = ContactQuerySet(self.model, using=self._db).active()
        return contacts

    def djangoql(self, search, schema=None):
        return self.get_queryset().djangoql(search, schema=schema)


class Contact(ClusterableModel):
    uuid = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        "users.User",
        on_delete=models.CASCADE,
        related_name="contact",
        blank=True,
        null=True,
    )
    first_name = models.CharField(max_length=255, blank=True, null=True)
    last_name = models.CharField(max_length=255, blank=True, null=True)
    email = models.EmailField(unique=True)
    audiences = models.ManyToManyField(
        "newsletter.Audience",
        related_name="contacts",
    )
    is_active = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    objects = ContactQuerySet.as_manager()

    def __str__(self):
        return self.email

    def get_full_name(self):
        """
        Return the first_name plus the last_name, with a space in between.
        """
        full_name = "%s %s" % (self.first_name, self.last_name)
        return full_name.strip()

    def clean(self) -> None:
        super().clean()
        self.email = self.email.lower()

    def make_token(self):
        """Makes token using a `ContactActivationTokenGenerator`.
        :return: Token
        :rtype: str
        """
        return ContactActivationTokenGenerator().make_token(self)

    def check_token(self, token):
        """Checks validity of the token.
        :param token: Token to validate e.g. `bkwxds-1d9acfc26be0a0e65b504cab0996718f`
        :type token: str
        :return: `True` if valid, `False` otherwise
        :rtype: bool
        """
        return ContactActivationTokenGenerator().check_token(self, token)

    def send_activation_email(self, request):
        """Sends activation email to the contact."""
        root_url = request.tenant.default_site.root_url
        email_settings = EmailSettings.load(request)
        context = {
            "absolute_url": root_url,
            "salutation": f"{self.first_name} {self.last_name}",
            "site_name": request.tenant.default_site.site_name,
            "activate_url": urljoin(
                root_url,
                reverse(
                    "birdsong:activate",
                    kwargs={"uuid": self.uuid, "token": self.make_token()},
                ),
            ),
            "email_settings": email_settings,
            "brand_settings": BrandSettings.load(request),
        }
        html_message = render_to_string(
            "newsletter/mail/activation_email.html", context
        )
        subject = settings.NEWSLETTER_ACTIVATION_EMAIL_SUBJECT
        if email_settings.email_subject_prefix:
            subject = f"{email_settings.email_subject_prefix} {subject}"

        return send_mail(
            subject,
            html_to_plaintext(html_message),
            settings.DEFAULT_FROM_EMAIL,
            [self.email],
            html_message=html_message,
        )


class ContactActivationTokenGenerator(PasswordResetTokenGenerator):
    """Strategy object used to generate and check tokens for the Contact subscription mechanism.
    NOTE: It extends :class:`PasswordResetTokenGenerator` so that it can use its own hash value generator
    """

    def _make_hash_value(self, contact, timestamp):
        """Hash composed out a couple of contact related fields and a timestamp.
        It will be invalidated after contact activation because it utilizes the `is_active` contact field.
        NOTE: Typing `is_active` to boolean first is deliberate so that `None` works the same as `False` or `0`
        :param contact: Client object to generate the token for
        :type contact: class:`newsletter.models.Contact`
        :param timestamp: Time in seconds to use to make the hash
        :type timestamp: float
        :return: Hash value that will be used during token operations
        :rtype: str
        """
        return str(bool(contact.is_active)) + str(contact.pk) + str(timestamp)


class ContactSchema(DjangoQLSchema):
    exclude = (NewsletterPage, Receipt)

    def get_fields(self, model):
        if model == Contact:
            return [
                BoolField(name="is_customer"),
                "first_name",
                "last_name",
                "email",
                "user",
                "is_active",
            ]
        if model == Group:
            return ["name"]
        if model == User:
            return ["first_name", "last_name", "email", "customer", "groups"]
        if model == Customer:
            return [
                "street",
                "street_number",
                "postal_code",
                "city",
                "telephone_number",
                "point_of_sale",
            ]
        if model == PointOfSale:
            return ["name"]
        return super().get_fields(model)
