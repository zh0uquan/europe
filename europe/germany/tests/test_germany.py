import pytest

from ..germany import NAME

pytestmark = pytest.mark.france


def test_assert_name():
    assert NAME == "GERMANY"
