from django.db import models

class CommonBaseClass(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    is_archived = models.BooleanField(default=False)

    class Meta:
        abstract = True



# TODO: finish fields!
class Address(models.Model):
    address = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = 'Address'
        verbose_name_plural = 'Addresses'

    def __str__(self):
        return self.address

