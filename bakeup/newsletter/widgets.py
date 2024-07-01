from django.forms import Media, TextInput


class DjangoQLWidget(TextInput):
    """ """

    def __init__(self, attrs=None):
        super().__init__(attrs=attrs)

    def build_attrs(self, *args, **kwargs):
        attrs = super().build_attrs(*args, **kwargs)
        # attrs['data-controller'] = 'color'
        # attrs['data-color-theme-value'] = self.theme
        # attrs['data-color-swatches-value'] = json.dumps(swatches)
        return attrs

    @property
    def media(self):
        return Media(
            js=[
                # load the UI library
                "js/",
                # load controller JS
                "js/color-controller.js",
            ],
            css={
                "all": [
                    "https://cdn.jsdelivr.net/gh/mdbassit/Coloris@latest/dist/coloris.min.css"
                ]
            },
        )
