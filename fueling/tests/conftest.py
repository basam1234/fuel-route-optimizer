import pytest
from django.core.cache import cache

from fueling import data_cache


@pytest.fixture(autouse=True)
def _reset_state():
    cache.clear()
    data_cache._stations = None
    yield
    cache.clear()
    data_cache._stations = None