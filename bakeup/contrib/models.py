from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import gettext_lazy as _

from bakeup.core.models import CommonBaseClass


# TODO: finish fields!
class Address(models.Model):
    address = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = "Address"
        verbose_name_plural = "Addresses"

    def __str__(self):
        return self.address


class Note(CommonBaseClass):
    content = models.TextField(verbose_name=_("Note"))
    user = models.ForeignKey("users.User", on_delete=models.CASCADE)

    # Generic relation fields
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    def __str__(self):
        return self.content
