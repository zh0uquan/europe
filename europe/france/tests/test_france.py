from ..france import NAME
import pytest

pytestmark = pytest.mark.france


def test_assert_name():
    assert NAME == "FRANCE"
