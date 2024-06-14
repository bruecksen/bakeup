from typing import Set

from dal import autocomplete
from django.contrib.auth.mixins import AccessMixin
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import RedirectView
from taggit.models import Tag


class StaffPermissionsMixin(AccessMixin):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_staff:
            return super().dispatch(request, *args, **kwargs)
        return self.handle_no_permission()


class CustomerRequiredMixin(AccessMixin):
    login_url = "shop:login"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and hasattr(request.user, "customer"):
            return super().dispatch(request, *args, **kwargs)
        return self.handle_no_permission()


class SuccessURLAllowedHostsMixin:
    success_url_allowed_hosts: Set[str] = set()

    def get_success_url_allowed_hosts(self):
        return {self.request.get_host(), *self.success_url_allowed_hosts}


class GetNextPageMixin(SuccessURLAllowedHostsMixin):
    next_url_param_name = "next"

    def get_next_page(self):
        if (
            self.next_url_param_name in self.request.POST
            or self.next_url_param_name in self.request.GET
        ):
            next_url = self.request.POST.get(
                self.next_url_param_name,
                self.request.GET.get(self.next_url_param_name),
            )
            url_is_safe = url_has_allowed_host_and_scheme(
                url=next_url,
                allowed_hosts=self.get_success_url_allowed_hosts(),
                require_https=self.request.is_secure(),
            )
            if url_is_safe:
                return next_url


class NextUrlMixin(GetNextPageMixin):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["next"] = self.request.GET.get("next", "")
        return context

    def form_valid(self, *args, **kwargs):
        ret_val = super().form_valid(*args, **kwargs)
        next_page = self.get_next_page()
        if next_page:
            return HttpResponseRedirect(next_page)
        return ret_val

    def get_success_url(self, *args, **kwargs):
        ret_val = super().get_success_url(*args, **kwargs)
        next_page = self.get_next_page()
        if next_page:
            return next_page
        return ret_val


class HomeView(RedirectView):
    def get_redirect_url(self, *args, **kwargs):
        if self.request.user.is_authenticated:
            if self.request.user.is_staff:
                return reverse("workshop:workshop")
            else:
                return "/shop/"
        else:
            return "/shop/"


class TagAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_authenticated and not self.request.user.is_staff:
            return Tag.objects.none()

        qs = Tag.objects.all()

        if self.q:
            qs = qs.filter(name__istartswith=self.q)

        return qs

    def get_create_option(self, context, q):
        return []
