import pytest

from ..france import NAME

pytestmark = pytest.mark.france


def test_assert_name():
    assert NAME == "FRANCE"
