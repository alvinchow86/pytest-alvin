from .common import (    # noqa
    config_override_factory, freezer
)
from .database import (    # noqa
    testdatabase_factory, db, db_fixture_check
)
from .socket import (    # noqa
    socket_disabled
)


def pytest_addoption(parser):
    parser.addoption(
        '--reset-db', '--create-db', dest='reset_db', action="store_true", default=False,
        help="Reset db schema from scratch"
    )
