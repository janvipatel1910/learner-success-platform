import pytest
from scripts import seed_synthetic_data

from skillpulse.core.config import Settings


def test_synthetic_seed_is_blocked_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(environment="production")
    monkeypatch.setattr(seed_synthetic_data, "get_settings", lambda: settings)

    with pytest.raises(RuntimeError, match="blocked in production"):
        seed_synthetic_data.load_synthetic_data()
