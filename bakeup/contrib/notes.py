from django.apps import apps
from django.http import Http404
from django.shortcuts import get_object_or_404

# Models that can carry notes through the generic notes widget. To add notes
# somewhere else give the model a GenericRelation to Note and list it here.
NOTE_MODELS = {"shop.productiondayproduct"}


def get_note_target(model_label, object_id):
    if model_label not in NOTE_MODELS:
        raise Http404
    model = apps.get_model(model_label)
    return get_object_or_404(model, pk=object_id)


def can_change_note(user, note):
    return user.is_superuser or note.user_id == user.pk
