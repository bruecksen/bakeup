import datetime
import random
import string
import qrcode
import qrcode.image.svg
from io import BytesIO

from django.utils.html import mark_safe
from django.contrib.sites.shortcuts import get_current_site
from django.contrib.auth.models import AbstractUser
from django.db.models import CharField
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _




class User(AbstractUser):

    def __str__(self):
        return self.get_full_name() or self.username

    def get_absolute_url(self):
        """Get url for user's detail view.

        Returns:
            str: URL for user detail.

        """
        return reverse("shop:user-profile")

    @property
    def is_customer(self):
        return hasattr(self, 'customer')
    
    @property
    def short_name(self):
        if self.first_name and self.last_name:
            return "{} {}.".format(self.first_name, self.last_name[0])
        else:
            return self.first_name


class AbstractToken(models.Model):
    """Authentication token for user model"""

    # Secret string
    token = models.CharField(max_length=64, unique=True)
    # Time to live - number of days until token expiration
    ttl = models.IntegerField(default=30, help_text="Days till token expires")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True

    @classmethod
    def generate_token(cls):
        alphabet = string.ascii_lowercase + string.digits
        return ''.join(random.choices(alphabet, k=8))

    @property
    def is_expired(self):
        elapsed = datetime.datetime.now() - self.created_at
        if elapsed > datetime.timedelta(days=self.ttl):
            return True

    def get_full_url(self, request):
        return request.tenant.reverse(request, 'users:login-token', token=self.token)

    def qr_code_svg(self, request):
        return mark_safe(self.generate_qr_code(request))

    
    def token_url(self, request):
        full_url = self.get_full_url(request)
        return mark_safe("<a href='{}'>{}</a>".format(full_url, full_url))

    def generate_qr_code(self, request):
        full_url = self.get_full_url(request)
        factory = qrcode.image.svg.SvgImage
        img = qrcode.make(full_url, image_factory=factory, box_size=20)
        stream = BytesIO()
        img.save(stream)
        html = "<div style='background-color: white;display: inline-block;'>{}</div>".format(stream.getvalue().decode())
        return html



class Token(AbstractToken):
    """Authentication token for user model"""
    user = models.OneToOneField(
        User,
        related_name='token',
        on_delete=models.CASCADE
    )

    def __str__(self):
        return "Token: {}".format(self.user)
    
    def get_full_url(self, request):
        return request.tenant.reverse(request, 'users:login-token', token=self.token)


class GroupToken(AbstractToken):
    """Authentication token for user model"""
    group = models.OneToOneField(
        'auth.Group',
        related_name='token',
        on_delete=models.CASCADE
    )

    def __str__(self):
        return "Token: {}".format(self.group)
    
    def get_full_url(self, request):
        return request.tenant.reverse(request, 'shop:signup', token=self.token)