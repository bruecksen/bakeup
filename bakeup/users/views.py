from typing import Any

from allauth.account import signals
from allauth.account.adapter import get_adapter
from allauth.account.forms import AddEmailForm, ChangePasswordForm
from allauth.account.utils import logout_on_password_change
from allauth.account.views import LoginView as _LoginView
from allauth.account.views import SignupView as _SignupView
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import Group
from django.contrib.messages.views import SuccessMessageMixin
from django.core.mail import send_mail
from django.db.models import ProtectedError
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import resolve, reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import DeleteView, DetailView

from bakeup.contrib.forms import MultiFormsView
from bakeup.newsletter.forms import NewsletterForm
from bakeup.newsletter.models import Audience, Contact
from bakeup.users.forms import TokenAuthenticationForm, UserProfileForm
from bakeup.users.models import Token

User = get_user_model()


class LoginView(_LoginView):
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.request.tenant.is_demo:
            kwargs["initial"] = {
                "login": settings.DEMO_LOGIN_USER,
                "password": settings.DEMO_LOGIN_PASSWORD,
            }
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        app_names = resolve(self.request.path).app_names
        if "shop" in app_names:
            context["base_template"] = "shop/base_page.html"
        else:
            context["form_token"] = TokenAuthenticationForm()
            context["base_template"] = "workshop/base.html"
        return context


class TokenLoginView(_LoginView):
    form_class = TokenAuthenticationForm
    template_name = "registration/token.html"

    def get(self, request, *args, **kwargs):
        token = kwargs.get("token", None)
        if token and Token.objects.filter(token=token).exists():
            user = Token.objects.get(token=token).user
            login(self.request, user, backend="core.backends.TokenBackend")
            return HttpResponseRedirect(self.get_success_url())
        else:
            return redirect("account_login")

    def get_success_url(self) -> str:
        if self.request.user.is_staff:
            return reverse("workshop:workshop")
        else:
            return "/shop/"

    def form_valid(self, form):
        """Security check complete. Log the user in."""
        login(self.request, form.get_user(), backend="core.backends.TokenBackend")
        return HttpResponseRedirect(self.get_success_url())


class SignupView(_SignupView):
    group = None

    def setup(self, request, *args, **kwargs):
        token = kwargs.get("token", None)
        if token and Group.objects.filter(token__token=token).exists():
            self.group = Group.objects.get(token__token=token)
        return super().setup(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(
            {
                "request": self.request,
            }
        )
        return kwargs

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        context_data["group"] = self.group
        return context_data

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.group and self.user:
            # add user to group if group available
            self.user.groups.add(self.group)
        if "newsletter" in form.cleaned_data and form.cleaned_data["newsletter"]:
            contact, created = Contact.objects.get_or_create(
                email__iexact=self.user.email,
                defaults={
                    "email": self.user.email,
                    "first_name": self.user.first_name,
                    "last_name": self.user.last_name,
                    "audience": Audience.objects.filter(is_default=True).first(),
                    "user": self.user,
                },
            )
            if not contact.is_active:
                contact.send_activation_email(self.request)
        return response


class UserProfileView(LoginRequiredMixin, DetailView):
    login_url = "shop:login"
    model = User

    def get_object(self):
        return self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["base_template"] = "workshop/base.html"
        context["update_url"] = reverse("users:update")
        return context


class ShopUserProfileView(UserProfileView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["base_template"] = "shop/base.html"
        context["update_url"] = reverse("shop:user-update")
        return context


user_profile_view = UserProfileView.as_view()
shop_user_profile_view = ShopUserProfileView.as_view()


class UserUpdateView(LoginRequiredMixin, SuccessMessageMixin, MultiFormsView):
    form_classes = {
        "user_profile": UserProfileForm,
        "add_email": AddEmailForm,
        "change_password": ChangePasswordForm,
        "newsletter": NewsletterForm,
    }

    success_message = "Daten erfolgreich aktualisiert"
    template_name = "users/user_profile.html"

    def get_success_url(self):
        assert (
            self.request.user.is_authenticated
        )  # for mypy to know that the user is authenticated
        return reverse("users:update")

    def get_object(self):
        return self.request.user

    def get_user_profile_initial(self):
        return {
            "first_name": self.request.user.first_name,
            "last_name": self.request.user.last_name,
            "point_of_sale": self.request.user.customer.point_of_sale,
            "street": self.request.user.customer.street,
            "street_number": self.request.user.customer.street_number,
            "postal_code": self.request.user.customer.postal_code,
            "city": self.request.user.customer.city,
            "telephone_number": self.request.user.customer.telephone_number,
            "newsletter": False,  # we use the initial data to hide the newsletter field
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["base_template"] = "workshop/base.html"
        return context

    def get_form_kwargs(self, form_name, bind_form):
        kwargs = super().get_form_kwargs(form_name, bind_form=bind_form)
        if form_name in ("add_email", "change_password"):
            kwargs.update(
                {
                    "user": self.request.user,
                }
            )
        elif form_name == "user_profile":
            kwargs.update({"request": self.request})
        return kwargs

    def newsletter_form_valid(self, form, *args, **kwargs):
        if form.cleaned_data["is_subscribed"]:
            contact, created = Contact.objects.get_or_create(
                email__iexact=self.request.user.email,
                defaults={
                    "email": self.request.user.email,
                    "first_name": self.request.user.first_name,
                    "last_name": self.request.user.last_name,
                    "audience": Audience.objects.filter(is_default=True).first(),
                    "user": self.request.user,
                },
            )
            if not contact.is_active:
                contact.send_activation_email(self.request)
        else:
            contact = Contact.objects.filter(email__iexact=self.request.user.email)
            if contact.exists():
                contact.delete()
        return HttpResponseRedirect(self.get_success_url())

    def add_email_form_valid(self, form, *args, **kwargs):
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

    def user_profile_form_valid(self, form, *args, **kwargs):
        first_name = form.cleaned_data["first_name"]
        last_name = form.cleaned_data["last_name"]
        user = self.request.user
        user.first_name = first_name
        user.last_name = last_name
        user.save(update_fields=["first_name", "last_name"])
        form.update_customer(user, self.request)
        messages.add_message(
            self.request, messages.INFO, "Daten erfolgreich aktualisiert"
        )
        return HttpResponseRedirect(self.get_success_url())

    def change_password_form_valid(self, form, *args, **kwargs):
        form.save()
        logout_on_password_change(self.request, form.user)
        get_adapter(self.request).add_message(
            self.request,
            messages.SUCCESS,
            "account/messages/password_changed.txt",
        )
        signals.password_changed.send(
            sender=self.request.user.__class__,
            request=self.request,
            user=self.request.user,
        )
        return HttpResponseRedirect(self.get_success_url())


class ShopUserUpdateView(UserUpdateView):
    login_url = "shop:login"

    def get_success_url(self):
        return reverse("shop:user-profile")

    def get_object(self):
        return self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["base_template"] = "shop/base_page.html"
        return context


user_update_view = UserUpdateView.as_view()
shop_user_update_view = ShopUserUpdateView.as_view()


class UserProfileDeleteView(DeleteView):
    model = User
    template_name = "users/user_profile_delete.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["orders_deleted"] = self.request.user.customer.orders.planned()
        context["orders_locked"] = self.request.user.customer.orders.upcoming().locked()
        return context

    def get_success_url(self):
        return "/shop/"

    def get_object(self):
        return self.request.user

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        try:
            self.object.customer.orders.planned().delete()
            self.object.is_active = False
            self.object.save()
            logout(request)
            client = request.tenant
            domain = client.get_primary_domain().domain
            subject = "Ein Konto auf {} wurde geschlossen".format(domain)
            body = (
                "Hallo, \n\nDer folgende Account wurde auf {} geschlossen: {}\n\nBitte"
                " löschen/anonymisieren Sie alle persönlichen Daten.\n\nViele"
                " Grüße\nBakeup.org".format(domain, self.object.email)
            )
            send_mail(
                subject,
                body,
                settings.DEFAULT_FROM_EMAIL,
                [settings.DEFAULT_FROM_EMAIL],
                fail_silently=False,
            )
            messages.add_message(request, messages.INFO, _("Your account is closed."))
        except ProtectedError as e:
            messages.error(request, e)
        finally:
            return redirect(success_url)
