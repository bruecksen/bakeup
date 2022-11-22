from django.urls import reverse
from django.contrib.sites.shortcuts import get_current_site

from allauth.account.adapter import DefaultAccountAdapter


class AccountAdapter(DefaultAccountAdapter):

    def get_signup_redirect_url(self, request):
        if request.user.is_staff:
            return reverse('workshop:workshop')
        else:
            return reverse('shop:shop')

    def send_confirmation_mail(self, request, emailconfirmation, signup):
        current_site = get_current_site(request)
        activate_url = self.get_email_confirmation_url(request, emailconfirmation)
        ctx = {
            "user": emailconfirmation.email_address.user,
            "activate_url": activate_url,
            "current_site": current_site,
            "key": emailconfirmation.key,
            "current_tenant": request.tenant,
            "current_tenant_domain": request.tenant.get_absolute_primary_domain(request),
        }
        if signup:
            email_template = "account/email/email_confirmation_signup"
        else:
            email_template = "account/email/email_confirmation"
        self.send_mail(email_template, emailconfirmation.email_address.email, ctx)