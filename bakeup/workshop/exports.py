from django.db.models import Q
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.views.generic import ListView
from django_filters.views import FilterView

from bakeup.contrib.export import ExportMixin
from bakeup.core.views import StaffPermissionsMixin
from bakeup.shop.models import Customer, CustomerOrder, ProductionDay
from bakeup.workshop.tables import CustomerOrderFilter


class CustomerReady2OrderExportView(StaffPermissionsMixin, ExportMixin, FilterView):
    filterset_class = CustomerOrderFilter
    model = Customer

    def get_headers(self):
        headers = [
            "kundennummer",
            "kunde",
            "kundengruppe",
            "email",
            "notizen",
            "rechnung_vorname",
            "rechnung_nachname",
            "rechnung_straße",
            "rechnung_plz",
            "rechnung_stadt",
            "rechnung_telefon",
        ]
        return headers

    def get_data(self):
        customers = self.object_list.order_by("pk")
        rows = []
        for customer in customers:
            rows.append(
                [
                    customer.id,
                    customer.user.get_full_name(),
                    "Kunden",
                    customer.user.email,
                    "",
                    customer.user.first_name,
                    customer.user.last_name,
                    customer.address_line,
                    customer.postal_code,
                    customer.city,
                    customer.telephone_number,
                ]
            )
        return rows

    @property
    def export_name(self):
        return "ready2order-{}".format(now().strftime("%d-%m-%Y"))


class CustomerBillbeeExportView(StaffPermissionsMixin, ExportMixin, FilterView):
    filterset_class = CustomerOrderFilter
    model = Customer

    def get_headers(self):
        headers = [
            "Nummer",
            "Bezeichnung",
            "Email (Standard)",
            "Email (Kaufm. Dokumente)",
            "Email (Statusänderungen)",
            "E-Mail Adressen",
            "Tel1",
            "Tel2",
            "Fax",
            "Telefonnummern",
            "Bemerkung",
            "Vorname",
            "Name",
            "Name2",
            "Firma",
            "Strasse",
            "Hausnummer",
            "Adresszusatz",
            "Bundesland",
            "PLZ",
            "Stadt",
            "Land",
            "USt.Id",
            "Sprache",
            "Typ",
            "Preisgruppe",
            "Adresstyp",
        ]
        return headers

    def get_data(self):
        customers = self.object_list.order_by("pk")
        rows = []
        for customer in customers:
            rows.append(
                [
                    customer.id,
                    customer.user.get_full_name(),
                    customer.user.email,
                    "",
                    "",
                    "",
                    customer.telephone_number,
                    "",
                    "",
                    "",
                    "",
                    customer.user.first_name,
                    customer.user.last_name,
                    "",
                    "",
                    customer.street,
                    customer.street_number,
                    "",
                    "",
                    customer.postal_code,
                    customer.city,
                    "Deutschland",
                    "",
                    "",
                    "Endkunde",
                    "",
                    "Rechnungsadresse",
                ]
            )
        return rows

    @property
    def export_name(self):
        return "billbee-kunden-{}".format(now().strftime("%d-%m-%Y"))


class CustomerSevdeskExportView(StaffPermissionsMixin, ExportMixin, FilterView):
    filterset_class = CustomerOrderFilter
    model = Customer

    def get_headers(self):
        headers = [
            "Kunden-Nr.",
            "Anrede",
            "Titel",
            "Nachname",
            "Vorname",
            "Organisation",
            "Namenszusatz",
            "Position",
            "Kategorie",
            "IBAN",
            "BIC",
            "Umsatzsteuer-ID",
            "Strasse",
            "PLZ",
            "Ort",
            "Land",
            "Adress-Kategorie",
            "Telefon",
            "Telefon-Kategorie",
            "Mobil",
            "Fax",
            "E-Mail",
            "E-Mail-Kategorie",
            "Webseite",
            "Webseiten-Kategorie",
            "Beschreibung",
            "Geburtstag",
            "Tags",
            "Debitoren-Nr",
            "Kreditoren-Nr.",
            "Leitweg-ID / Leitwegsnummer",
            "Steuernummer",
            "Skonto Tage",
            "Skonto Prozent",
            "Zahlungsziel Tage",
            "Kundenrabatt",
            "Ist Kundenrabatt prozentual",
        ]
        return headers

    def get_data(self):
        customers = self.object_list.order_by("pk")
        rows = []
        for customer in customers:
            rows.append(
                [
                    customer.id,
                    "",
                    "",
                    customer.user.last_name,
                    customer.user.first_name,
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    customer.address_line,
                    customer.postal_code,
                    customer.city,
                    "Deutschland",
                    "",
                    customer.telephone_number,
                    "",
                    "",
                    "",
                    customer.user.email,
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                ]
            )
        return rows

    @property
    def export_name(self):
        return "sevDesk-{}".format(now().strftime("%d-%m-%Y"))


class ProductionDayExportView(StaffPermissionsMixin, ExportMixin, ListView):
    model = CustomerOrder
    template_name = "workshop/order_list.html"

    def setup(self, request, *args, **kwargs):
        self.production_day = ProductionDay.objects.get(pk=kwargs.get("pk"))
        return super().setup(request, *args, **kwargs)

    def get_data(self):
        column_count = (
            6 + self.production_day.production_day_products.published().count()
        )
        rows = []
        top_header = [""] * column_count
        top_header[0] = "Produktionstag"
        top_header[1] = self.production_day.day_of_sale
        rows.append(top_header)
        rows.append([""] * column_count)
        headers = ["Nachname", "Vorname", "E-Mail", "Telefonnummer"]
        production_day_products = (
            self.production_day.production_day_products.published()
        )
        for product in production_day_products:
            headers.append(product.product.get_short_name())
        headers.append("Abholstelle")
        headers.append("Anmerkung")
        rows.append(headers)
        for order in self.object_list.all():
            row = []
            row.extend(
                [
                    order.customer.user.last_name,
                    order.customer.user.first_name,
                    order.customer.user.email,
                    order.customer.telephone_number,
                ]
            )
            for product in production_day_products:
                order_position = order.positions.filter(
                    Q(product=product.product)
                    | Q(product__product_template=product.product)
                ).first()
                row.append(order_position and order_position.quantity or 0)
            pos = order.point_of_sale and order.point_of_sale.get_short_name() or ""
            row.append(pos)
            row.append(
                order.notes.first() and order.notes.first().content or "",
            )
            rows.append(row)
        # add footer

        rows.append([""] * column_count)
        footer = [
            "",
            "",
            "",
            "",
            "",
        ]
        footer2 = [
            "",
            "",
            "",
            "",
            "",
        ]
        for product in production_day_products:
            footer.append(product.get_order_quantity())
            footer2.append(product.max_quantity)
        footer.append("")
        footer2.append("")
        rows.append(footer)
        rows.append(footer2)
        return rows

    def get_headers(self):
        return []

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(production_day=self.production_day)

    @property
    def export_name(self):
        return _("productionday-{}").format(
            self.production_day.day_of_sale.strftime("%d-%m-%Y")
        )


class CustomerOrderBillbeeExportView(StaffPermissionsMixin, ExportMixin, FilterView):
    filterset_class = CustomerOrderFilter
    model = CustomerOrder

    def get_headers(self):
        headers = [
            "Nr.",
            "Artikel-Nr.",
            "Bestell-Datum",
            "Bezahlmethode",
            "Artikel",
            "Variante",
            "Einzelpreis Netto",
            "Einzelpreis Brutto",
            "Versandkosten Netto",
            "Versandkosten Brutto",
            "Nachnahmegebühr",
            "MwSt. %",
            "Anzahl",
            "Preis Netto",
            "Preis Brutto",
            "Währung",
            "Versand-Datum",
            "Rechn. Firma",
            "Rechn. Anrede",
            "Rechn. Nachname",
            "Rechn. Mittelname",
            "Rechn. Vorname",
            "Rechn. Adresszusatz",
            "Rechn. Straße",
            "Rechn. Postleitzahl",
            "Rechn. Stadt",
            "Rechn. Bundesland",
            "Rechn. Land",
            "Rechn. Telefon",
            "Rechn. E-Mail",
            "Rechn. Anmerkung",
            "USt-IdNr.",
            "Geburtsdatum",
            "Kundennummer",
            "Lief. Firma",
            "Lief. Anrede",
            "Lief. Nachname",
            "Lief. Mittelname",
            "Lief. Vorname",
            "Lief. Adresszusatz",
            "Lief. Straße",
            "Lief. Postleitzahl",
            "Lief. Stadt",
            "Lief. Bundesland",
            "Lief. Land",
            "Lief. Telefon",
            "Lief. E-Mail",
            "Lief. Anmerkung",
        ]
        return headers

    def get_data(self):
        customer_orders = self.object_list.order_by("pk")
        rows = []
        for customer_order in customer_orders:
            for customer_order_position in customer_order.positions.all():
                rows.append(
                    [
                        customer_order_position.order.id,
                        customer_order_position.product.pk,
                        customer_order.created,
                        "",  # Bezahlmethode
                        customer_order_position.product.name,
                        "",  # Variante
                        "",  # Einzelpreis Netto
                        customer_order_position.price,  # Einzelpreis Brutto
                        "0",  # Versandkosten Netto
                        "0",  # Versandkosten Brutto
                        "0",  # Nachnahmegebühr
                        "7",  # MwSt. %
                        customer_order_position.quantity,
                        "",  # Preis Netto
                        customer_order_position.price_total,  # Preis Brutto
                        "EUR",
                        "",  # Versand-Datum
                        "",  # Rechn. Firma
                        "",  # Rechn. Anrede
                        customer_order.customer.user.last_name,  # Rechn. Nachname
                        "",
                        customer_order.customer.user.first_name,  # Rechn. Vorname
                        "",  # Rechn. Adresszusatz
                        customer_order.customer.address_line,  # Rechn. Straße
                        customer_order.customer.postal_code,
                        customer_order.customer.city,
                        "",
                        "Deutschland",
                        customer_order.customer.telephone_number,
                        customer_order.customer.user.email,
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                    ]
                )
            return rows

    @property
    def export_name(self):
        return "billbee-bestellungen-{}".format(now().strftime("%d-%m-%Y"))
