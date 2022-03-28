from django.shortcuts import render
from django.contrib.auth.mixins import AccessMixin


class StaffPermissionsMixin(AccessMixin):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_staff:
            return super().dispatch(request, *args, **kwargs)
        return self.handle_no_permission()