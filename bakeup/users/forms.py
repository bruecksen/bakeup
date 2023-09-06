from django import forms
from django.contrib.auth import forms as admin_forms
from django.contrib.auth import get_user_model, authenticate
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.conf import settings

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, HTML

from allauth.utils import set_form_field_order
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
    

class UserFormMixin():
    
    def __init__(self, request, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in request.tenant.clientsetting.user_registration_fields:
            field_settings = settings.USER_REGISTRATION_FORM_FIELDS.get(field)
            self.fields[field] = forms.CharField(**field_settings)
        if PointOfSale.objects.count() > 1:
            self.fields["point_of_sale"] = forms.ModelChoiceField(queryset=PointOfSale.objects.all(), label="Abholstelle", help_text="Bitte wähle eine Abholstelle aus.", empty_label=None)
            if PointOfSale.objects.filter(is_primary=True).exists():
                self.fields["point_of_sale"].initial = PointOfSale.objects.get(is_primary=True)
        elif 'point_of_sale' in self.fields:
            del self.fields['point_of_sale']
        if hasattr(self, "field_order"):
            set_form_field_order(self, self.field_order)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.disable_csrf = False
        self.helper.layout = Layout(
            'email',
            'password1',
            'point_of_sale',
            'first_name',
            'last_name',
            Row(
                Column('street', css_class='form-group col-md-8 mb-0'),
                Column('street_number', css_class='form-group col-md-4 mb-0'),
                css_class='form-row'
            ),
            Row(
                Column('postal_code', css_class='form-group col-md-4 mb-0'),
                Column('city', css_class='form-group col-md-8 mb-0'),
                css_class='form-row'
            ),
            'telephone_number',
        )

    def update_customer(self, user):
        if 'point_of_sale' in self.cleaned_data:
            user.customer.point_of_sale = self.cleaned_data['point_of_sale']
        if 'street' in self.cleaned_data:
            user.customer.street = self.cleaned_data['street']
        if 'street_number' in self.cleaned_data:
            user.customer.street_number = self.cleaned_data['street_number']
        if 'postal_code' in self.cleaned_data:
            user.customer.postal_code = self.cleaned_data['postal_code']
        if 'city' in self.cleaned_data:
            user.customer.city = self.cleaned_data['city']
        if 'telephone_number' in self.cleaned_data:
            user.customer.telephone_number = self.cleaned_data['telephone_number']
        user.customer.save()

    def save(self, request):
        user = super().save(request)
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.save(update_fields=['first_name', 'last_name'])
        self.update_customer(user)
        return user
            

class SignupForm(UserFormMixin, _SignupForm):
    pass


class UserProfileForm(UserFormMixin, forms.Form):
    pass

