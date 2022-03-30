from django import forms
from django.forms.formsets import BaseFormSet
from django.forms import formset_factory

from bakeup.workshop.models import Product


class CustomerOrderForm(forms.Form):
    production_day_id = forms.IntegerField(widget=forms.HiddenInput())
    product_id = forms.IntegerField(widget=forms.HiddenInput())
    quantity = forms.IntegerField()
