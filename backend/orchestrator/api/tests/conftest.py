import pytest
from api.config.settings import settings

@pytest.fixture(autouse=True)
def force_mocks(monkeypatch):
    monkeypatch.setattr(settings, "USE_MOCK_C1", True)
    monkeypatch.setattr(settings, "USE_MOCK_C3", True)
