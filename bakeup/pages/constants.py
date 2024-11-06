EMAIL_ORDER_CONFIRM_DEFAULT = """
<p>Vielen Dank für Ihre Bestellung, {{ first_name }} {{ last_name }}!</p>
<p>Hier eine Übersicht über Ihre Bestellung für den {{ production_day }}:<br>
<br>
<br>
<strong>{{ order }}</strong>
<br>
<br>
Gesamtpreis: <strong>{{ price_total }}</strong><br>
</p>
<p>Ihre ausgewählte Abholstelle: <strong>{{ point_of_sale }}</strong></p>
<p>Sie können Ihre Bestellung vor dem Backtag jederzeit in Ihrem Account unter {{ order_link }} anpassen oder stornieren.</p>
"""  # noqa: E501

EMAIL_ORDER_CANCELLATION_DEFAULT = """
<p>Sie haben soeben Ihre komplette Bestellung für den <strong>{{ production_day }}</strong> gelöscht. Wenn dies ein Versehen war, bestellen Sie die gelöschten Backwaren bitte wieder neu.</p>
"""  # noqa: E501
