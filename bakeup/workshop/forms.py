from crispy_forms.helper import FormHelper
from crispy_forms.layout import HTML, Column, Fieldset, Layout, Row
from dal import autocomplete, forward
from django import forms
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.forms import (
    BooleanField,
    CharField,
    ChoiceField,
    DecimalField,
    FloatField,
    Form,
    IntegerField,
    ModelChoiceField,
    ModelForm,
    Textarea,
    formset_factory,
    inlineformset_factory,
)
from django.utils.translation import gettext_lazy as _

from bakeup.core.models import UOM
from bakeup.shop.models import (
    Customer,
    CustomerOrder,
    PointOfSale,
    PointOfSalePickupTime,
    ProductionDay,
)
from bakeup.users.models import User
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
            "is_recurring",
            "max_recurring_order_qty",
            "max_order_qty",
            "is_bio_certified",
            "price_display",
            "vat_rate",
            "dough_temperature",
            "mixer_warming",
        ]
        labels = {"is_sellable": _("Sold in the shop")}
        help_texts = {
            "is_sellable": _(
                "Customers can order it. Leave unchecked for ingredients and doughs."
            )
        }
        widgets = {
            "tags": autocomplete.TaggitSelect2("workshop:tag-autocomplete"),
            "uom": forms.Select(attrs={"class": "form-select"}),
            "vat_rate": forms.Select(attrs={"class": "form-select"}),
            "weight": forms.NumberInput(attrs={"class": "form-control numberinput"}),
            "dough_temperature": forms.NumberInput(
                attrs={"class": "form-control numberinput", "step": "0.1"}
            ),
            "mixer_warming": forms.NumberInput(
                attrs={"class": "form-control numberinput", "step": "0.1"}
            ),
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
        if not self.instance.uom_id:
            self.initial.setdefault("uom", UOM.get_default())
        # An empty field uses the default, the placeholder shows it.
        self.fields["dough_temperature"].widget.attrs["placeholder"] = (
            settings.DOUGH_TEMPERATURE_DEFAULT
        )
        self.fields["mixer_warming"].widget.attrs["placeholder"] = (
            settings.MIXER_WARMING_DEFAULT
        )

    def clean_sku(self):
        sku = self.cleaned_data["sku"]
        if sku:
            products = Product.objects.filter(sku=sku)
            if self.instance:
                products = products.exclude(pk=self.instance.pk)
            if products.exists():
                raise ValidationError(_("A product with the SKU already exists"))
        return sku


class WaterTemperatureForm(Form):
    # The temperatures of the water temperature calculator of a plan step, one
    # field per ingredient besides the water. An empty field uses the default.
    dough = FloatField(required=False, label=_("Dough temperature"))
    warming = FloatField(required=False, label=_("Mixer warming"))

    def __init__(self, *args, water, **kwargs):
        # `water` is the calculation of the step, see ProductionPlan.get_water.
        super().__init__(*args, **kwargs)
        self.water = water
        self.initial.setdefault("dough", water["dough"])
        self.initial.setdefault("warming", water["warming"])
        for row in water["rows"]:
            self.fields[self.row_field_name(row)] = FloatField(
                required=False, label=row["name"], initial=row["temperature"]
            )
        for field in self.fields.values():
            field.widget.attrs.update(
                {"class": "form-control", "step": "0.1", "inputmode": "decimal"}
            )

    @staticmethod
    def row_field_name(row):
        return f"row_{row['row'].pk}"

    def rows(self):
        return [
            {"row": row, "field": self[self.row_field_name(row)]}
            for row in self.water["rows"]
        ]

    def get_temperatures(self):
        # In the format of ProductionPlan.temperatures, without empty fields.
        temperatures = {
            key: self.cleaned_data[key]
            for key in ["dough", "warming"]
            if self.cleaned_data[key] is not None
        }
        temperatures["rows"] = {
            str(row["row"].pk): self.cleaned_data[self.row_field_name(row)]
            for row in self.water["rows"]
            if self.cleaned_data[self.row_field_name(row)] is not None
        }
        return temperatures


def ingredient_choices(product=None):
    paths = list(
        Category.objects.filter(
            slug__in=["dough", "preparations", "ingredients"]
        ).values_list("path", flat=True)
    )
    if not paths:
        return Product.objects.none()
    query = Q()
    for path in paths:
        query |= Q(category__path__startswith=path)
    products = Product.objects.filter(query)
    if product:
        products = (
            products.exclude(pk=product.pk)
            .exclude(pk__in=product.childs.values("parent"))
            .exclude(pk__in=product.parents.values("child"))
        )
    return products


class AddIngredientForm(Form):
    NEW_PREFIX = "new:"

    weight = FloatField(localize=True, label=_("Weight"))
    ingredient = CharField(
        label=_("Ingredient"),
        widget=autocomplete.Select2(
            url="workshop:ingredient-autocomplete",
            attrs={
                "data-placeholder": _("Search or create ingredient"),
                "data-minimum-input-length": 0,
                "data-width": "100%",
            },
        ),
    )
    category = ModelChoiceField(
        queryset=Category.objects.all(),
        required=False,
        empty_label=_("Select a category"),
    )

    def __init__(self, *args, product=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.product = product
        if product:
            self.fields["ingredient"].widget.forward = [
                forward.Const(product.pk, "parent")
            ]
        if not self.is_bound:
            self.initial.setdefault(
                "category", Category.objects.filter(slug="ingredients").first()
            )

    def clean_weight(self):
        weight = self.cleaned_data["weight"]
        if weight <= 0:
            raise ValidationError(_("Please enter a valid weight."))
        return weight

    def clean(self):
        cleaned_data = super().clean()
        value = cleaned_data.get("ingredient", "")
        cleaned_data["product"] = None
        cleaned_data["new_name"] = None
        if value.startswith(self.NEW_PREFIX):
            name = value[len(self.NEW_PREFIX) :].strip()
            if not name:
                self.add_error("ingredient", _("Please select an ingredient."))
            elif not cleaned_data.get("category"):
                self.add_error(
                    "category", _("Please select a category for the new product.")
                )
            cleaned_data["new_name"] = name
        elif value:
            product = None
            if value.isdigit():
                product = ingredient_choices(self.product).filter(pk=value).first()
            if not product or not product.weight_in_base_unit:
                self.add_error("ingredient", _("Please select an ingredient."))
            cleaned_data["product"] = product
        return cleaned_data


class SelectProductForm(Form):
    product = ModelChoiceField(queryset=Product.objects.all())


UNIT_GRAM = "g"
UNIT_PERCENT = "percent"
UNIT_CHOICES = [(UNIT_GRAM, "g"), (UNIT_PERCENT, "%")]


class ProductHierarchyForm(Form):
    amount = FloatField(localize=True)
    unit = ChoiceField(choices=UNIT_CHOICES, required=False)


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


class ProductDoughYieldForm(Form):
    dough_yield = IntegerField(min_value=100, label=_("Hydration"))


class ProductSaltForm(Form):
    salt = DecimalField(
        decimal_places=2,
        min_value=0,
        max_value=100,
        label=_("Salt"),
        localize=True,
    )


class ProductPreFermentForm(Form):
    pre_ferment = DecimalField(
        decimal_places=2,
        min_value=0,
        max_value=100,
        label=_("Fermented Flour"),
        localize=True,
    )


class ProductTotalDoughWeightForm(Form):
    total_dough_weight = DecimalField(
        decimal_places=2,
        min_value=0,
        label=_("Dough Weight"),
        localize=True,
    )


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
    first_name = CharField(label=_("First name"))
    last_name = CharField(label=_("Last name"))
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


class CustomerCreateForm(CustomerForm):
    email = forms.EmailField()
    send_invite = forms.BooleanField(
        required=False,
        label=_("Send password reset email"),
        help_text=_(
            "Send the customer an email with a link to set their own password."
        ),
    )

    class Meta(CustomerForm.Meta):
        fields = ["email"] + CustomerForm.Meta.fields

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError(_("A user with this email already exists."))
        return email


class PointOfSaleForm(ModelForm):
    class Meta:
        model = PointOfSale
        fields = [
            "name",
            "short_name",
            "is_primary",
            "is_internal",
            "street",
            "street_number",
            "postal_code",
            "city",
            "description",
            "latitude",
            "longitude",
        ]
        widgets = {
            "description": Textarea(attrs={"rows": 3}),
            # Set by the pin on the map in the template.
            "latitude": forms.HiddenInput(),
            "longitude": forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.disable_csrf = True
        self.helper.layout = Layout(
            Fieldset(
                _("General"),
                "name",
                "short_name",
                "is_primary",
                "is_internal",
            ),
            Fieldset(
                _("Address"),
                Row(
                    Column("street", css_class="form-group col-md-8 mb-0"),
                    Column("street_number", css_class="form-group col-md-4 mb-0"),
                    css_class="form-row",
                ),
                Row(
                    Column("postal_code", css_class="form-group col-md-4 mb-0"),
                    Column("city", css_class="form-group col-md-8 mb-0"),
                    css_class="form-row",
                ),
            ),
            Fieldset(
                _("Pick-up times"),
                # The formset comes from the view, see PointOfSaleFormMixin.
                HTML('{% include "workshop/includes/pickup_time_formset.html" %}'),
            ),
            Fieldset(
                _("Information for customers"),
                "description",
            ),
            "latitude",
            "longitude",
        )


class PointOfSalePickupTimeForm(ModelForm):
    class Meta:
        model = PointOfSalePickupTime
        fields = ["day_of_the_week", "from_time", "to_time"]
        widgets = {
            "day_of_the_week": forms.Select(attrs={"class": "form-select"}),
            "from_time": forms.TimeInput(
                format="%H:%M", attrs={"type": "time", "class": "form-control"}
            ),
            "to_time": forms.TimeInput(
                format="%H:%M", attrs={"type": "time", "class": "form-control"}
            ),
        }


PointOfSalePickupTimeFormSet = inlineformset_factory(
    PointOfSale,
    PointOfSalePickupTime,
    form=PointOfSalePickupTimeForm,
    extra=0,
    can_delete=True,
)


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


class ReminderMessageForm(ModelForm):
    """A pickup email in its editor: who it is for, subject and text. points
    are the points of sale to choose from, dicts of get_points. The orders
    are looked up when it is sent, see bakeup/workshop/reminders.py."""

    ALL = "all"
    POINTS = "points"

    recipients = forms.ChoiceField(
        choices=[(ALL, ALL), (POINTS, POINTS)],
        initial=ALL,
        widget=forms.RadioSelect,
    )
    points = forms.MultipleChoiceField(
        required=False, widget=forms.CheckboxSelectMultiple
    )
    subject = forms.CharField(widget=forms.TextInput, label=_("Subject"))

    class Meta:
        model = ReminderMessage
        fields = ["subject", "body"]
        labels = {"body": _("Text")}

    def __init__(self, *args, points=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.point_list = list(points)
        self.fields["points"].choices = [
            (point["key"], point["name"]) for point in self.point_list
        ]

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("recipients") == self.POINTS and not cleaned_data.get(
            "points"
        ):
            self.add_error("points", _("Choose at least one point of sale."))
        return cleaned_data

    @property
    def selection(self):
        """The keys of the chosen points, empty for all orders."""
        if self.cleaned_data.get("recipients") == self.POINTS:
            return set(self.cleaned_data.get("points") or [])
        return set()
