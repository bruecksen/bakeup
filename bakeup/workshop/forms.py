from dal import autocomplete
from django import forms
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.forms import (
    BooleanField,
    CharField,
    DecimalField,
    FloatField,
    Form,
    IntegerField,
    ModelChoiceField,
    ModelForm,
    Textarea,
    formset_factory,
)
from django.utils.translation import gettext_lazy as _

from bakeup.core.models import UOM
from bakeup.shop.models import Customer, CustomerOrder, PointOfSale, ProductionDay
from bakeup.workshop.models import Category, Product, ProductionPlan, ReminderMessage


class ProductForm(ModelForm):
    price = DecimalField(
        max_digits=14,
        decimal_places=2,
        required=False,
        label=_("Price"),
        widget=forms.NumberInput(attrs={"class": "form-control numberinput"}),
    )
    uom = ModelChoiceField(
        queryset=UOM.objects,
        empty_label=None,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = Product
        fields = [
            "name",
            "display_name",
            "sku",
            "description",
            "image",
            "image_secondary",
            "video_file",
            "category",
            "tags",
            "weight",
            "uom",
            "is_sellable",
            "is_buyable",
            "is_composable",
            "is_recurring",
            "max_recurring_order_qty",
            "max_order_qty",
            "is_bio_certified",
        ]
        widgets = {
            "tags": autocomplete.TaggitSelect2("workshop:tag-autocomplete"),
            "uom": forms.Select(attrs={"class": "form-select"}),
            "weight": forms.NumberInput(attrs={"class": "form-control numberinput"}),
        }

    def __init__(self, *args, **kwargs):
        instance = kwargs.get("instance", None)
        if instance:
            kwargs.update(
                initial={
                    "price": instance.sale_price and instance.sale_price.price.amount
                }
            )
        super().__init__(*args, **kwargs)

    def clean_sku(self):
        sku = self.cleaned_data["sku"]
        if sku:
            products = Product.objects.filter(sku=sku)
            if self.instance:
                products = products.exclude(pk=self.instance.pk)
            if products.exists():
                raise ValidationError(_("A product with the SKU already exists"))
        return sku


class AddProductForm(Form):
    weight = FloatField(required=True, label=_("Weight"))
    product_existing = ModelChoiceField(
        queryset=Product.objects.all(),
        required=False,
        empty_label=_("Select existing product"),
    )
    product_new = CharField(required=False, label=_("New product name"))
    category = ModelChoiceField(
        queryset=Category.objects.all(),
        required=False,
        empty_label=_("Select a category"),
    )
    is_sellable = BooleanField(label=_("Sellable?"), required=False)
    is_buyable = BooleanField(label=_("Buyable?"), required=False)
    is_composable = BooleanField(label=_("Composable?"), required=False)

    def __init__(self, product=None, parent_products=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        products = Product.objects.filter(
            Q(category__path__startswith=Category.objects.get(slug="dough").path)
            | Q(
                category__path__startswith=Category.objects.get(
                    slug="preparations"
                ).path
            )
            | Q(
                category__path__startswith=Category.objects.get(slug="ingredients").path
            )
        )
        if parent_products:
            products = products.exclude(
                pk__in=parent_products.values_list("parent__pk", flat=True)
            )
        if product:
            products = products.exclude(pk=product.pk)
        self.fields["product_existing"].queryset = products


AddProductFormSet = formset_factory(AddProductForm, extra=0)


class SelectProductForm(Form):
    product = ModelChoiceField(queryset=Product.objects.all())


class ProductHierarchyForm(Form):
    amount = FloatField(localize=True)


class ProductionPlanDayForm(Form):
    production_day = ModelChoiceField(
        queryset=ProductionDay.objects.all(),
        widget=forms.Select(
            attrs={"onchange": "this.form.submit()", "class": "form-select"}
        ),
    )


class ProductionPlanForm(ModelForm):
    class Meta:
        model = ProductionPlan
        fields = ("start_date", "duration")


class ProductKeyFiguresForm(Form):
    fermentation_loss = DecimalField(
        decimal_places=2,
        min_value=0,
        max_value=100,
        label=_("Fermentation Loss"),
        localize=True,
    )
    dough_yield = IntegerField(
        min_value=100, label=_("Hydration"), disabled=True, required=False
    )
    salt = DecimalField(
        decimal_places=2,
        min_value=0,
        max_value=100,
        label=_("Salt"),
        disabled=True,
        required=False,
        localize=True,
    )
    starter = DecimalField(
        decimal_places=2,
        min_value=0,
        max_value=100,
        label=_("Starter"),
        disabled=True,
        required=False,
    )
    wheat = CharField(
        disabled=True,
        required=False,
        widget=Textarea(
            attrs={
                "rows": 2,
            }
        ),
        label=_("Flour"),
    )
    pre_ferment = DecimalField(
        decimal_places=2,
        min_value=0,
        max_value=100,
        disabled=True,
        required=False,
        localize=True,
        label=_("Fermented Flour"),
    )
    total_dough_weight = DecimalField(
        decimal_places=2,
        min_value=0,
        disabled=True,
        required=False,
        localize=True,
        label=_("Dough Weight"),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if (
            "initial" in kwargs
            and "wheat" in kwargs["initial"]
            and kwargs["initial"]["wheat"]
        ):
            line_count = kwargs["initial"]["wheat"].count("\n")
            self.fields["wheat"].widget.attrs["rows"] = line_count + 1


class SelectProductionDayForm(Form):
    select_production_day = ModelChoiceField(
        queryset=ProductionDay.objects.all(), empty_label=_("Select production day")
    )


class CustomerForm(ModelForm):
    first_name = CharField()
    last_name = CharField()
    is_active = BooleanField(
        required=False,
        label=_("active"),
        help_text=_(
            "Designates whether this user should be treated as active. "
            "Unselect this instead of deleting accounts."
        ),
    )
    groups = forms.ModelMultipleChoiceField(
        required=False,
        queryset=Group.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        label=_("Groups"),
        help_text=_("This user belongs to the following groups."),
    )

    class Meta:
        model = Customer
        fields = [
            "is_active",
            "first_name",
            "last_name",
            "point_of_sale",
            "street",
            "street_number",
            "postal_code",
            "city",
            "telephone_number",
            "groups",
        ]


class CustomerOrderForm(ModelForm):
    production_day = forms.IntegerField(required=False, widget=forms.HiddenInput)
    customer = forms.ModelChoiceField(
        label=_("Customer"),
        required=True,
        widget=autocomplete.ModelSelect2(
            url="workshop:customer-autocomplete", forward=["production_day"]
        ),
        queryset=Customer.objects.all(),
    )

    class Meta:
        model = CustomerOrder
        fields = ["customer", "point_of_sale"]
        help_texts = {
            "point_of_sale": _(
                "If you leave this empty, it uses the default point of sale for the"
                " customer."
            ),
        }


class ProductionDayMetaProductForm(forms.Form):
    meta_product = forms.CharField(widget=forms.HiddenInput, label=_("Source Product"))
    meta_product_name = forms.CharField(
        disabled=True, required=False, label=_("Source Product")
    )
    product = forms.ModelChoiceField(
        queryset=Product.objects.filter(
            category__name__iexact=settings.META_PRODUCT_CATEGORY_NAME
        ),
        required=False,
        label=_("Target Product"),
    )

    def __init__(self, *args, **kwargs):
        self.production_day = kwargs.pop("production_day")
        super().__init__(*args, **kwargs)
        self.fields["product"].queryset = Product.objects.filter(
            production_days__production_day=self.production_day
        )


ProductionDayMetaProductformSet = formset_factory(
    form=ProductionDayMetaProductForm, extra=0
)


class ProductionDayReminderForm(forms.Form):
    point_of_sale = forms.ModelChoiceField(
        empty_label=_("All"),
        queryset=PointOfSale.objects.all(),
        required=False,
        label=_("Point of sale"),
        help_text=_(
            "Send emails to orders of specific point of sale, leave empty to send to"
            " all point of sales."
        ),
    )
    subject = forms.CharField(required=True)
    body = forms.CharField(
        required=True,
        widget=forms.Textarea,
        help_text=(
            "Mögliche Tags: {{ site_name }}, {{ first_name }}, {{ last_name }}, {{"
            " email }}, {{ order }}, {{ price_total }}, {{ production_day }}, {{"
            " order_count }}, {{ order_link }}"
        ),
    )


class ReminderMessageForm(ModelForm):
    point_of_sale = forms.ModelChoiceField(
        empty_label="All",
        queryset=PointOfSale.objects.all(),
        required=False,
        label=_("Point of sale"),
    )
    subject = forms.CharField(widget=forms.TextInput)
    production_day = forms.HiddenInput()

    class Meta:
        model = ReminderMessage
        fields = ["subject", "body", "point_of_sale", "production_day"]

    # def __init__(self, *args, **kwargs):
    #     production_day = kwargs.pop('production_day', None)
    #     super().__init__(*args, **kwargs)
    #     if production_day:
    #         self.fields['messages'].queryset = ReminderMessage.objects.filter(production_day=production_day)


class SelectReminderMessageForm(forms.Form):
    message = forms.ModelChoiceField(
        queryset=ReminderMessage.objects.none(),
        required=False,
        label=_("Create a new message or select a saved one"),
        empty_label=_("Create a new message"),
    )

    def __init__(self, *args, **kwargs):
        production_day = kwargs.pop("production_day", None)
        super().__init__(*args, **kwargs)
        if production_day:
            self.fields["message"].queryset = ReminderMessage.objects.filter(
                production_day=production_day, state=ReminderMessage.State.PLANNED
            )
