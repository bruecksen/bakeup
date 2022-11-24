from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView, RedirectView, UpdateView, FormView
from django.shortcuts import redirect

from allauth.account.adapter import get_adapter
from allauth.account.views import LoginView as _LoginView, EmailView
from allauth.account.forms import AddEmailForm, ChangePasswordForm
from allauth.account import signals

from bakeup.users.forms import TokenAuthenticationForm, UserProfileForm
from bakeup.users.models import Token
from bakeup.shop.forms import CustomerForm

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
            return redirect('account_login')

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


class UserUpdateView(LoginRequiredMixin, SuccessMessageMixin, FormView):

    model = User
    fields = ["first_name", "last_name"]
    success_message = "Daten erfolgreich aktualisiert"
    form_class = UserProfileForm
    template_name = 'users/user_profile.html'

    def get_success_url(self):
        assert (
            self.request.user.is_authenticated
        )  # for mypy to know that the user is authenticated
        return self.request.user.get_absolute_url()

    def get_object(self):
        return self.request.user

    def get_initial(self):
        initial = super().get_initial()
        initial.update({
            'first_name': self.request.user.first_name,
            'last_name': self.request.user.last_name,
            'point_of_sale': self.request.user.customer.point_of_sale,
        })
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['base_template'] = "workshop/base.html"
        if self.request.method.lower() == 'post':
            context['add_email_form'] = AddEmailForm(data=self.request.POST, user=self.get_object())
            context['form'] = self.get_form()
        else:
            context['add_email_form'] = AddEmailForm()
            context['change_password_form'] = ChangePasswordForm()
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if 'add-email' in request.POST:
            form = AddEmailForm(data=request.POST, user=self.get_object())
            if form.is_valid():
                email_address = form.save(self.request)
                get_adapter(self.request).add_message(
                    self.request,
                    messages.INFO,
                    "account/messages/email_confirmation_sent.txt",
                    {"email": form.cleaned_data["email"]},
                )
                signals.email_added.send(
                    sender=self.request.user.__class__,
                    request=self.request,
                    user=self.request.user,
                    email_address=email_address,
                )
                return HttpResponseRedirect(self.get_success_url())
            else:
                return self.render_to_response(self.get_context_data())
        else:
            return super().post(request, *args, **kwargs)

    def form_valid(self, form, *args, **kwargs):
        first_name = form.cleaned_data['first_name']
        last_name = form.cleaned_data['last_name']
        point_of_sale = form.cleaned_data['point_of_sale']
        user = self.request.user
        user.first_name = first_name
        user.last_name = last_name
        user.save(update_fields=['first_name', 'last_name'])
        user.customer.point_of_sale = point_of_sale
        user.customer.save(update_fields=['point_of_sale'])
        return super().form_valid(form, *args, **kwargs)

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