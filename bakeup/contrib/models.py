from django.db import models


# TODO: finish fields!
class Address(models.Model):
    address = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = "Address"
        verbose_name_plural = "Addresses"

    def __str__(self):
        return self.address
