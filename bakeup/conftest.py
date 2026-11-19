import sys
from pathlib import Path

import pytest
from django.db import connection
from django_tenants.test.client import TenantClient
from django_tenants.utils import get_tenant_domain_model, get_tenant_model

from bakeup.users.models import User
from bakeup.users.tests.factories import UserFactory

# Like manage.py and config/wsgi.py, so settings paths such as
# "core.renderers.CustomFieldRenderer" resolve.
sys.path.append(str(Path(__file__).resolve().parent))

TEST_SCHEMA = "fast_test"
TEST_DOMAIN = "tenant.fast-test.com"


@pytest.fixture(autouse=True)
def media_storage(settings, tmpdir):
    settings.MEDIA_ROOT = tmpdir.strpath


@pytest.fixture
def user() -> User:
    return UserFactory()


@pytest.fixture(scope="session")
def tenant(django_db_setup, django_db_blocker):
    # The schema of FastTenantTestCase: created and migrated once, then reused.
    with django_db_blocker.unblock():
        tenant = get_tenant_model().objects.filter(schema_name=TEST_SCHEMA).first()
        if tenant is None:
            tenant = get_tenant_model()(schema_name=TEST_SCHEMA, name="Test")
            tenant.save(verbosity=0)
            get_tenant_domain_model().objects.create(
                tenant=tenant, domain=TEST_DOMAIN, is_primary=True
            )
    return tenant


@pytest.fixture
def tenant_db(db, tenant):
    connection.set_tenant(tenant)
    yield tenant
    connection.set_schema_to_public()


@pytest.fixture
def client(tenant_db, settings):
    settings.ALLOWED_HOSTS = [*settings.ALLOWED_HOSTS, TEST_DOMAIN]
    return TenantClient(tenant_db)
