import sys
from pathlib import Path

import pytest

from bakeup.users.models import User
from bakeup.users.tests.factories import UserFactory

# Like manage.py and config/wsgi.py, so settings paths such as
# "core.renderers.CustomFieldRenderer" resolve.
sys.path.append(str(Path(__file__).resolve().parent))


@pytest.fixture(autouse=True)
def media_storage(settings, tmpdir):
    settings.MEDIA_ROOT = tmpdir.strpath


@pytest.fixture
def user() -> User:
    return UserFactory()
