from freezegun import freeze_time
import pytest


@pytest.fixture
def freezer():
    """
    Use freezegun in pytest fixture style
    """
    with freeze_time() as freezer:
        yield freezer
