"""Fixtures for Govee Cloud tests."""

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Load custom_components in every test."""
    return


@pytest.fixture(autouse=True)
def no_throttle_delay(monkeypatch):
    """Don't pace commands in tests."""
    monkeypatch.setattr("custom_components.govee_cloud.throttle.MIN_INTERVAL", 0)
    monkeypatch.setattr("custom_components.govee_cloud.api.ACCOUNT_MIN_INTERVAL", 0)
