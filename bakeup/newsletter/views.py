import json
import os

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import SuspiciousOperation
from django.db import IntegrityError, transaction
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.encoding import force_str
from django.utils.translation import gettext as _
from django.utils.translation import ngettext
from django.views.decorators.http import require_http_methods
from wagtail.admin.forms.search import SearchForm
from wagtail.log_actions import log
from wagtail.models import Site

from bakeup.contrib.utils import get_json_http_response
from bakeup.newsletter.forms import SubscribeForm
from bakeup.newsletter.models import (
    Audience,
    Contact,
    NewsletterListPage,
    NewsletterRecipients,
)
from bakeup.users.models import User

from .forms import (
    ConfirmContactImportForm,
    ConfirmImportManagementForm,
    ContactImportForm,
)
from .utils import (
    get_file_storage,
    get_format_cls_by_extension,
    get_import_formats,
    get_supported_extensions,
    write_to_file_storage,
)


def recipients(request):
    recipients: NewsletterRecipients = get_object_or_404(
        NewsletterRecipients,  # type: ignore
        pk=request.GET.get("pk"),
    )

    return JsonResponse(
        {
            "name": recipients.name,
            "member_count": recipients.member_count,
        }
    )


def unsubscribe_user(request, uuid, list_id=None):
    try:
        contact = Contact.objects.get(uuid=uuid)
    except Contact.DoesNotExist:
        return redirect(
            "home"
        )  # unable to identify contact, let's pretend this endpoint doesn't exist
    contact.delete()
    list_page = None
    if list_id:
        list_page = get_object_or_404(NewsletterListPage, id=list_id)

    return render(
        request,
        "newsletter/unsubscribe.html",
        context={
            "list": list_page,
            "contact": contact,
        },
    )


def activate(request, uuid, token):
    """Subscription activation endpoint
    :param request: Request sent to this endpoint
    :type request: class:`requests.models.Request`
    :param contact_pk: Contact PK (e.g. "33")
    :type cid: str
    :param token: Subscription Activation Token (e.g. "bkwxpq-cc9a685f0e58c20baacf0ce2c93823f3")
    :type token: str
    :return: Rendered activation confirmation template as an HTTP Response
    :rtype: class:`django.http.HttpResponse`
    """
    try:
        contact = get_object_or_404(Contact, uuid=uuid)
    except Contact.DoesNotExist:
        raise Http404  # unable to identify contact, let's pretend this endpoint doesn't exist

    if not contact.check_token(token):  # token not valid?
        raise Http404  # invalid token, let's pretend this endpoint doesn't exist

    if not contact.is_active:  # contact not active yet?
        contact.is_active = True
        contact.save()

    return render(
        request,
        "newsletter/activate.html",
        context={
            "site": Site.find_for_request(request),
            "site_name": settings.WAGTAIL_SITE_NAME,
            "contact": contact,
        },
    )


def subscribe_api(request):
    """Preferred subscription endpoint (alternative to `/subscribe`) when JavaScript (Ajax) is available
    :param request: Request sent to this endpoint
    :type request: class:`requests.models.Request`
    :return: HTTP Response with JSON body
    :rtype: class:`django.http.HttpResponse`
    """
    if request.method == "POST":
        contact = None
        try:
            if (
                request.headers.get("Content-Type") == "application/json"
            ):  # is json request?
                encoding = request.POST.get("_encoding", "utf-8")
                body_data = json.loads(request.body.decode(encoding))
                form = SubscribeForm(body_data)
                if form.is_valid():
                    with transaction.atomic():
                        contact, created = Contact.objects.get_or_create(
                            email=form.cleaned_data["email"],
                            defaults={
                                "first_name": form.cleaned_data.get("first_name", ""),
                                "last_name": form.cleaned_data.get("last_name", ""),
                            },
                        )  # create a new contact instance
                        contact.audiences.add(
                            Audience.objects.filter(is_default=True).first()
                        )
                        msg = settings.NEWSLETTER_SUBSCRIBE_FORM_MSG_SUCCESS
                        if not contact.is_active:
                            contact.send_activation_email(request)
                            msg += settings.NEWSLETTER_ACTIVATION_REQUIRED_MSG
                        return get_json_http_response(msg)
                else:
                    return get_json_http_response(
                        settings.NEWSLETTER_SUBSCRIBE_FORM_MSG_FAILURE,
                        success=False,
                        errors=form.errors.as_json(),
                    )
        except IntegrityError as e:  # "Already Subscribed" exception?
            raise e
            # # i.e. django.db.utils.IntegrityError: UNIQUE constraint failed: birdsong_contact.email
            # if contact:
            #     contact.delete()
            # if (DUPLICATE_EMAIL_EXCEPTION in str(e) or DUPLICATE_KEY_VALUE in str(e)): # email already subscribed?
            #     msg = settings.NEWSLETTER_SUBSCRIBE_FORM_MSG_SUCCESS
            #     return get_json_http_response(msg) # obfuscate "Already Subscribed" error as success

    return get_json_http_response(
        _("Bad request"), success=False, status=400
    )  # assume bad request at this point


def start_contact_import(request):
    supported_extensions = get_supported_extensions()
    from_encoding = "utf-8"

    query_string = request.GET.get("q", "")

    if request.POST or request.FILES:
        form_kwargs = {}
        form = ContactImportForm(
            supported_extensions,
            request.POST or None,
            request.FILES or None,
            **form_kwargs,
        )
    else:
        form = ContactImportForm(supported_extensions)

    if not request.FILES or not form.is_valid():
        return render(
            request,
            "newsletter/choose_import_file.html",
            {
                "search_form": SearchForm(
                    data={"q": query_string} if query_string else None,
                    placeholder=_("Search redirects"),
                ),
                "form": form,
            },
        )

    import_file = form.cleaned_data["import_file"]

    _name, extension = os.path.splitext(import_file.name)
    extension = extension.lstrip(".")

    if extension not in supported_extensions:
        messages.error(
            request,
            _('File format of type "%(extension)s" is not supported')
            % {"extension": extension},
        )
        return redirect("wagtailredirects:start_import")

    import_format_cls = get_format_cls_by_extension(extension)
    input_format = import_format_cls()
    file_storage = write_to_file_storage(import_file, input_format)

    try:
        data = file_storage.read(input_format.get_read_mode())
        if not input_format.is_binary() and from_encoding:
            data = force_str(data, from_encoding)
        dataset = input_format.create_dataset(data)
    except UnicodeDecodeError as e:
        messages.error(
            request,
            _("Imported file has a wrong encoding: %(error_message)s")
            % {"error_message": e},
        )
        return redirect("wagtailredirects:start_import")
    except Exception as e:  # noqa: BLE001; pragma: no cover
        messages.error(
            request,
            _("%(error)s encountered while trying to read file: %(filename)s")
            % {"error": type(e).__name__, "filename": import_file.name},
        )
        return redirect("wagtailredirects:start_import")

    # This data is needed in the processing step, so it is stored in
    # hidden form fields as signed strings (signing happens in the form).
    initial = {
        "import_file_name": os.path.basename(file_storage.name),
        "input_format": get_import_formats().index(import_format_cls),
    }

    return render(
        request,
        "newsletter/confirm_import.html",
        {
            "form": ConfirmContactImportForm(dataset.headers, initial=initial),
            "dataset": dataset,
        },
    )


@require_http_methods(["POST"])
def process_contact_import(request):
    supported_extensions = get_supported_extensions()
    from_encoding = "utf-8"

    management_form = ConfirmImportManagementForm(request.POST)
    if not management_form.is_valid():
        # Unable to unsign the hidden form data, or the data is missing, that's suspicious.
        raise SuspiciousOperation(
            "Invalid management form, data is missing or has been tampered with:\n"
            f"{management_form.errors.as_text()}"
        )

    input_format = get_import_formats()[
        int(management_form.cleaned_data["input_format"])
    ]()

    FileStorage = get_file_storage()
    file_storage = FileStorage(name=management_form.cleaned_data["import_file_name"])

    data = file_storage.read(input_format.get_read_mode())
    if not input_format.is_binary() and from_encoding:
        data = force_str(data, from_encoding)
    dataset = input_format.create_dataset(data)

    # Now check if the rest of the management form is valid
    form = ConfirmContactImportForm(
        dataset.headers,
        request.POST,
        request.FILES,
        initial=management_form.cleaned_data,
    )

    if not form.is_valid():
        return render(
            request,
            "newsletter/confirm_import.html",
            {
                "form": form,
                "dataset": dataset,
            },
        )

    import_summary = create_contacts_from_dataset(
        dataset,
        {
            "email": int(form.cleaned_data["email"]),
            "first_name": int(form.cleaned_data["first_name"]),
            "last_name": int(form.cleaned_data["last_name"]),
            "audience": form.cleaned_data["audience"],
            "is_active": form.cleaned_data["is_active"],
        },
    )

    file_storage.remove()

    if import_summary["errors_count"] > 0:
        return render(
            request,
            "newsletter/import_summary.html",
            {
                "form": ContactImportForm(supported_extensions),
                "import_summary": import_summary,
            },
        )

    total = import_summary["total"]
    messages.success(
        request,
        ngettext("Imported %(total)d redirect", "Imported %(total)d redirects", total)
        % {"total": total},
    )

    return redirect("contact:index")


def create_contacts_from_dataset(dataset, config):
    errors = []
    successes = 0
    total = 0

    for row in dataset:
        total += 1

        data = {
            "email": row[config["email"]],
            "first_name": row[config["first_name"]],
            "last_name": row[config["last_name"]],
            "is_active": config["is_active"],
        }

        with transaction.atomic():
            try:
                contact, created = Contact.objects.get_or_create(
                    email__iexact=row[config["email"]], defaults=data
                )
                contact.audiences.add(config["audience"])
                if not contact.user:
                    user = User.objects.filter(email__iexact=contact.email).first()
                    if user:
                        contact.user = user
                        contact.save()
                if config["is_active"]:
                    contact.is_active = True
                    contact.save()
                log(instance=contact, action="wagtail.create")
            except IntegrityError as e:
                errors.append([row[config["email"]], str(e)])
                continue

        successes += 1

    return {
        "errors": errors,
        "errors_count": len(errors),
        "successes": successes,
        "total": total,
    }
