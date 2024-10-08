from allauth.account.adapter import DefaultAccountAdapter
from django.contrib import messages
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import EmailMessage
from django.http import HttpResponseRedirect
from django.template import Context, Template, TemplateDoesNotExist
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_str
from django.utils.translation import gettext_lazy as _

from bakeup.pages.models import BrandSettings, EmailSettings, GeneralSettings


class AccountAdapter(DefaultAccountAdapter):
    def get_login_redirect_url(self, request):
        if request.user.is_staff:
            return reverse("workshop:workshop")
        else:
            general_settings = GeneralSettings.load(request_or_site=self.request)
            if general_settings.login_redirect_url:
                return general_settings.login_redirect_url
            else:
                return "/shop/#backtag"

    def pre_login(self, request, user, **kwargs):
        if not user.is_active:
            messages.add_message(
                self.request,
                messages.INFO,
                _("This account is closed. Login is not possible."),
            )
            return HttpResponseRedirect("/shop/")
        else:
            return super().pre_login(request, user, **kwargs)

    def get_signup_redirect_url(self, request):
        if request.user.is_staff:
            return reverse("workshop:workshop")
        else:
            return "/shop/"

    def get_email_confirmation_redirect_url(self, request):
        if request.user.is_staff:
            return reverse("workshop:workshop")
        else:
            return "/shop/"

    def send_confirmation_mail(self, request, emailconfirmation, signup):
        current_site = get_current_site(request)
        activate_url = self.get_email_confirmation_url(request, emailconfirmation)
        ctx = {
            "user": emailconfirmation.email_address.user,
            "activate_url": activate_url,
            "current_site": current_site,
            "key": emailconfirmation.key,
            "current_tenant": request.tenant,
            "current_tenant_domain": request.tenant.get_absolute_primary_domain(
                request
            ),
        }
        if signup:
            email_template = "account/email/email_confirmation_signup"
        else:
            email_template = "account/email/email_confirmation"
        self.send_mail(email_template, emailconfirmation.email_address.email, ctx)

    def render_mail(self, template_prefix, email, context, headers=None):
        """
        Renders an email to `email`.  `template_prefix` identifies the
        email that is to be sent, e.g. "account/email/email_confirmation"
        """
        to = [email] if isinstance(email, str) else email
        context["brand_settings"] = BrandSettings.load(request_or_site=self.request)
        context["email_settings"] = EmailSettings.load(request_or_site=self.request)
        context["absolute_url"] = self.request.tenant.default_full_url
        subject = render_to_string("{0}_subject.txt".format(template_prefix), context)
        # remove superfluous line breaks
        subject = " ".join(subject.splitlines()).strip()
        subject = self.format_email_subject(subject)

        from_email = self.get_from_email()

        body = None
        try:
            template_name = "{0}_message.txt".format(template_prefix)
            body = render_to_string(
                template_name,
                context,
                self.request,
            ).strip()
            # bodies[ext] = email_settings.get_body_with_footer(bodies[ext])
        except TemplateDoesNotExist:
            if not body:
                # We need at least one body
                raise
        msg = EmailMessage(subject, body, from_email, to, headers=headers)
        msg.content_subtype = "html"  # Main content is now text/html
        return msg

    def format_email_subject(self, subject):
        email_settings = EmailSettings.load(request_or_site=self.request)
        prefix = ""
        if email_settings.email_subject_prefix:
            prefix = email_settings.get_subject_with_prefix(subject)
            t = Template(prefix)
            subject = t.render(Context({"site_name": self.request.tenant.name}))
            return force_str(subject)
        return force_str(subject)
