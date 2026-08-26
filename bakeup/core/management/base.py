import logging

from django.core.management.base import BaseCommand
from django.db import connection
from django_tenants.utils import get_tenant_model, schema_exists

logger = logging.getLogger(__name__)


class PerTenantCommand(BaseCommand):
    """Base for commands run per-tenant via ``all_tenants_command``.

    Isolates each tenant so one tenant's failure never aborts the whole batch.
    Genuine failures are logged at ERROR (reported to Sentry as an event);
    failures caused by a tenant being rebuilt/deleted (schema or ``Client`` row
    missing, e.g. the daily ``demo`` rebuild dropping its schema mid-run) are
    logged at INFO (breadcrumb only, no Sentry event).

    Subclasses implement ``handle_tenant(tenant, *args, **options)`` and use the
    passed-in ``tenant`` (the in-memory ``connection.tenant`` the loop already
    set) instead of re-querying by ``schema_name``.
    """

    def handle(self, *args, **options):
        tenant = getattr(connection, "tenant", None)
        schema_name = connection.schema_name
        if tenant is None:
            logger.warning("%s ran without a tenant; skipping.", type(self).__name__)
            return
        try:
            self.handle_tenant(tenant, *args, **options)
        except Exception:
            if self._tenant_is_being_rebuilt(schema_name):
                logger.info(
                    "Skipping tenant '%s' for %s: schema/row missing "
                    "(being rebuilt or deleted).",
                    schema_name,
                    type(self).__name__,
                )
            else:
                logger.exception(
                    "%s failed for tenant '%s'.",
                    type(self).__name__,
                    schema_name,
                )
            # Never re-raise: let all_tenants_command continue to the next tenant.

    @staticmethod
    def _tenant_is_being_rebuilt(schema_name):
        try:
            if not schema_exists(schema_name):
                return True
            return (
                not get_tenant_model().objects.filter(schema_name=schema_name).exists()
            )
        except Exception:
            # If even this check fails, err toward reporting the original error.
            return False

    def handle_tenant(self, tenant, *args, **options):
        raise NotImplementedError
