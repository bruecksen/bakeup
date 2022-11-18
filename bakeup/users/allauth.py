from django.urls import reverse

from allauth.account.adapter import DefaultAccountAdapter


class AccountAdapter(DefaultAccountAdapter):

    def get_signup_redirect_url(self, request):
        if request.user.is_staff:
            return reverse('workshop:workshop')
        else:
            return reverse('shop:shop')