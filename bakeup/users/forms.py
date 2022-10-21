from django import forms
from django.contrib.auth import forms as admin_forms
from django.contrib.auth import get_user_model, authenticate
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError

User = get_user_model()


class TokenAuthenticationForm(forms.Form):
    token = forms.CharField(
        label=_("Token"),
        strip=False,
    )

    def __init__(self, request=None, *args, **kwargs):
        """
        The 'request' parameter is set for custom auth use by subclasses.
        The form data comes in via the standard 'data' kwarg.
        """
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean(self):
        token = self.cleaned_data.get('token')

        if token:
            self.user_cache = authenticate(self.request, token=token)
            if self.user_cache is None:
                return ValidationError(
                    "Please enter a valid token.",
                    code='invalid_login',
                )
        return self.cleaned_data

    def get_user(self):
        return self.user_cache
