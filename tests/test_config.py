"""Tests for the config module."""

import pytest
from pytest import MonkeyPatch

from scenaraist.config import Settings, load_settings


def test_settings_default_values(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv("GIGACHAT_CREDENTIALS", raising=False)

    with pytest.raises(ValueError, match="GIGACHAT_CREDENTIALS"):
        Settings()


def test_settings_with_credentials(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("GIGACHAT_CREDENTIALS", "test-creds")
    settings = Settings()
    assert settings.gigachat_credentials == "test-creds"


def test_settings_custom_model(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("GIGACHAT_CREDENTIALS", "test-creds")
    monkeypatch.setenv("GIGACHAT_MODEL", "GigaChat-Pro")
    settings = Settings()
    assert settings.gigachat_model == "GigaChat-Pro"


def test_settings_verify_ssl_true(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("GIGACHAT_CREDENTIALS", "test-creds")
    monkeypatch.setenv("GIGACHAT_VERIFY_SSL_CERTS", "true")
    settings = Settings()
    assert settings.verify_ssl_certs is True


def test_load_settings(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("GIGACHAT_CREDENTIALS", "test-creds")
    settings = load_settings()
    assert isinstance(settings, Settings)
    assert settings.gigachat_credentials == "test-creds"
