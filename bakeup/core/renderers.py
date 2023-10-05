from django_bootstrap5.renderers import FieldRenderer


class CustomFieldRenderer(FieldRenderer):
    def get_server_side_validation_classes(self):
        """Return CSS classes for server-side validation."""
        if self.field_errors:
            return self.error_css_class
        elif self.field.form.is_bound:
            return self.success_css_class
        return ""
