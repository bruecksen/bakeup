from django.contrib.auth import get_user_model, login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.views import LoginView as _LoginView
from django.views.generic import DetailView, RedirectView, UpdateView
from django.shortcuts import redirect

from bakeup.users.forms import TokenAuthenticationForm
from bakeup.users.models import Token

User = get_user_model()


class LoginView(_LoginView):
    def get_success_url(self) -> str:
        if self.request.user.is_staff:
            return reverse('workshop:workshop')
        else:
            return reverse('shop:shop')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_token'] = TokenAuthenticationForm()
        return context

class TokenLoginView(_LoginView):
    form_class = TokenAuthenticationForm
    template_name = "registration/token.html"

    def get(self, request, *args, **kwargs):
        token = kwargs.get('token', None)
        if token and Token.objects.filter(token=token).exists():
            user = Token.objects.get(token=token).user
            login(self.request, user, backend='core.backends.TokenBackend')
            return HttpResponseRedirect(self.get_success_url())
        else:
            return redirect('login')

    def get_success_url(self) -> str:
        if self.request.user.is_staff:
            return reverse('workshop:workshop')
        else:
            return reverse('shop:shop')

    def form_valid(self, form):
        """Security check complete. Log the user in."""
        login(self.request, form.get_user(), backend='core.backends.TokenBackend')
        return HttpResponseRedirect(self.get_success_url())



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