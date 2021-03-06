from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.views import LoginView as _LoginView
from django.views.generic import DetailView, RedirectView, UpdateView

User = get_user_model()


class LoginView(_LoginView):
    def get_success_url(self) -> str:
        if self.request.user.is_staff:
            return reverse('workshop:workshop')
        else:
            return reverse('shop:shop')
        return super().get_success_url()



class UserProfileView(LoginRequiredMixin, DetailView):
    model = User

    def get_object(self):
        return self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['base_template'] = "workshop/base.html"
        context['update_url'] = reverse('users:update')
        return context



class ShopUserProfileView(UserProfileView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['base_template'] = "shop/base.html"
        context['update_url'] = reverse('shop:user-update')
        return context



user_profile_view = UserProfileView.as_view()
shop_user_profile_view = ShopUserProfileView.as_view()


class UserUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):

    model = User
    fields = ["first_name", "last_name"]
    success_message = _("Information successfully updated")

    def get_success_url(self):
        assert (
            self.request.user.is_authenticated
        )  # for mypy to know that the user is authenticated
        return self.request.user.get_absolute_url()

    def get_object(self):
        return self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['base_template'] = "workshop/base.html"
        return context


class ShopUserUpdateView(UserUpdateView):

    def get_success_url(self):
        return reverse('shop:user-profile')

    def get_object(self):
        return self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['base_template'] = "shop/base.html"
        return context

user_update_view = UserUpdateView.as_view()
shop_user_update_view = ShopUserUpdateView.as_view()