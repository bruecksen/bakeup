from django.shortcuts import render
from django.contrib.auth.mixins import AccessMixin
from django.urls import reverse
from django.views.generic import RedirectView


class StaffPermissionsMixin(AccessMixin):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_staff:
            return super().dispatch(request, *args, **kwargs)
        return self.handle_no_permission()


class CustomerRequiredMixin(AccessMixin):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and hasattr(request.user, 'customer'):
            return super().dispatch(request, *args, **kwargs)
        return self.handle_no_permission()



class HomeView(RedirectView):
    def get_redirect_url(self, *args, **kwargs):
        if self.request.user.is_authenticated:
            if self.request.user.is_staff:
                return reverse('workshop:workshop')
            else:
                return reverse('shop:shop')
        else:
            return reverse('login')