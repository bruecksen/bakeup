from django.contrib.auth.backends import ModelBackend

from bakeup.users.models import Token

class TokenBackend(ModelBackend):
    def authenticate(self, request, token=None):
        try:
            t = Token.objects.get(token=token)
            if not t.user.is_staff and not t.user.is_superuser:
                return t.user
        except Token.DoesNotExist:
            return None
        return None