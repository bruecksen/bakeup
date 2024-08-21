from django import forms
from django.core.signing import BadSignature, Signer
from django.utils.translation import gettext_lazy as _


class NewsletterForm(forms.Form):
    is_subscribed = forms.BooleanField(required=False, label="Newsletter abonnieren")


class SubscribeForm(forms.Form):
    first_name = forms.CharField(label="Vorname", max_length=255, required=False)
    last_name = forms.CharField(label="Nachname", max_length=255, required=False)
    email = forms.EmailField(label="E-Mail", max_length=255)


class SendTestEmailForm(forms.Form):
    email = forms.EmailField(
        label="Email address",
        help_text="Send a test email to this address",
    )


class ContactImportForm(forms.Form):
    import_file = forms.FileField(
        label=_("File to import"),
    )

    def __init__(self, allowed_extensions, *args, **kwargs):
        super().__init__(*args, **kwargs)

        accept = ",".join([f".{x}" for x in allowed_extensions])
        self.fields["import_file"].widget = forms.FileInput(attrs={"accept": accept})

        uppercased_extensions = [x.upper() for x in allowed_extensions]
        allowed_extensions_text = ", ".join(uppercased_extensions)
        help_text = _("Supported formats: %(supported_formats)s.") % {
            "supported_formats": allowed_extensions_text,
        }
        self.fields["import_file"].help_text = help_text


class ConfirmImportManagementForm(forms.Form):
    """
    Store the import file name and input format in the form so that it can be used in the next step

    The initial values are signed, to prevent them from being tampered with.
    """

    import_file_name = forms.CharField(widget=forms.HiddenInput())
    input_format = forms.CharField(widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        self.signer = Signer()
        initial = kwargs.get("initial", {})
        for key in {"import_file_name", "input_format"}:
            if key in initial:
                # Sign initial data so it cannot be tampered with
                initial[key] = self.signer.sign(initial[key])
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        for key in {"import_file_name", "input_format"}:
            try:
                cleaned_data[key] = self.signer.unsign(cleaned_data[key])
            except BadSignature as e:
                raise forms.ValidationError(e.message)
        return cleaned_data


class ConfirmContactImportForm(ConfirmImportManagementForm):
    email = forms.ChoiceField(
        label=_("Email field"),
        choices=(),
    )
    first_name = forms.ChoiceField(
        label=_("First name field"),
        choices=(),
    )
    last_name = forms.ChoiceField(
        label=_("Last name field"),
        choices=(),
    )
    audience = forms.ModelChoiceField(
        label=_("Audience"),
        queryset=None,
        required=False,
    )
    is_active = forms.BooleanField(initial=True, required=False)

    def __init__(self, headers, *args, **kwargs):
        super().__init__(*args, **kwargs)

        choices = []
        for i, f in enumerate(headers):
            choices.append([str(i), f])
        if len(headers) > 1:
            choices.insert(0, ("", "---"))

        self.fields["email"].choices = choices
        self.fields["first_name"].choices = choices
        self.fields["last_name"].choices = choices
        from bakeup.newsletter.models import Audience

        self.fields["audience"].queryset = Audience.objects.all()
