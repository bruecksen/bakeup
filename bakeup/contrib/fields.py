from django.contrib.postgres.fields import ArrayField
from django.db.models import Model
from django.db.models.enums import TextChoices
from django.db.models.fields import CharField
from django.forms.fields import MultipleChoiceField


# Contribution by @cbows 
class _MultipleChoiceField(MultipleChoiceField):
    def __init__(self, *args, **kwargs):
        kwargs.pop("base_field", None)
        kwargs.pop("max_length", None)
        super().__init__(*args, **kwargs)


# Original contribution by @danni 
# slightly rewrited to match Django writing code style
class ChoiceArrayField(ArrayField):
    def formfield(self, **kwargs):
        return super().formfield(**{"form_class": _MultipleChoiceField,
                                    "choices": self.base_field.choices,
                                    **kwargs})