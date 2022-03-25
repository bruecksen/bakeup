from django.contrib import admin
from .models import PointOfSale, PointOfSaleOpeningHour
from bakeup.core.models import Address

admin.site.register(PointOfSale)
admin.site.register(PointOfSaleOpeningHour)
admin.site.register(Address)
