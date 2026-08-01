"""Pin the admin aggregator wiring."""

import pytest
from app.modules.admin.router import router


@pytest.mark.unit
def test_admin_router_prefix() -> None:
    assert router.prefix == "/admin"
