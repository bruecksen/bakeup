from django import forms
from django.contrib.auth import forms as admin_forms
from django.contrib.auth import get_user_model, authenticate
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError

from allauth.account.forms import SignupForm as _SignupForm

from bakeup.shop.models import PointOfSale

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
                raise ValidationError({"token": "Please enter a valid token."})
        return self.cleaned_data

    def get_user(self):
        return self.user_cache


class SignupForm(_SignupForm):
    # point_of_sale = forms.ModelChoiceField(queryset=PointOfSale.objects.all(), label="Depot")

    def __init__(self, *args, **kwargs):
        super(SignupForm, self).__init__(*args, **kwargs)
        if PointOfSale.objects.count() > 1:
            self.fields["point_of_sale"] = forms.ModelChoiceField(queryset=PointOfSale.objects.all(), label="Depot", help_text="Bitte wähle eine Abholstelle aus.", empty_label=None)
            if PointOfSale.objects.filter(is_primary=True).exists():
                self.fields["point_of_sale"].initial = PointOfSale.objects.get(is_primary=True)

    def save(self, request):

        # Ensure you call the parent class's save.
        # .save() returns a User object.
        user = super().save(request)

        if 'point_of_sale' in self.cleaned_data:
            user.customer.point_of_sale = self.cleaned_data['point_of_sale']
            user.customer.save(update_fields=['point_of_sale'])
        # You must return the original result.
        return user