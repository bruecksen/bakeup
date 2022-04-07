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



user_profile_view = UserProfileView.as_view()


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


user_update_view = UserUpdateView.as_view()