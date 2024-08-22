import json

from django.forms import Media, Textarea


class DjangoQLWidget(Textarea):
    """ """

    def __init__(self, attrs=None, introspections=None):
        self.introspections = introspections
        default_attrs = {"class": "djangoql-textarea"}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs)

    def build_attrs(self, *args, **kwargs):
        attrs = super().build_attrs(*args, **kwargs)
        attrs["data-controller"] = "djangoql"
        attrs["data-djangoql-introspections-value"] = json.dumps(self.introspections)
        return attrs

    @property
    def media(self):
        return Media(
            js=[
                # load the UI library
                "js/djangoql.js",
                # load controller JS
                "js/djangoql-controler.js",
            ],
            css={
                "all": [
                    "css/djangoql.css",
                ]
            },
        )
