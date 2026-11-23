"""Tests for fail-closed Alertmanager configuration rendering."""

from pathlib import Path

import pytest

from backend.scripts.render_alertmanager_config import render_alertmanager_config


def _write_env(path: Path, **values: str) -> Path:
    path.write_text(
        "\n".join(f"{key}={value}" for key, value in values.items()),
        encoding="utf-8",
    )
    return path


def test_production_renderer_rejects_default_internal_webhook(tmp_path, monkeypatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    env_file = _write_env(
        tmp_path / ".env.production",
        ENVIRONMENT="production",
        ALERT_EMAIL_TO="oncall@example.org",
    )

    with pytest.raises(ValueError, match="circular dummy webhook"):
        render_alertmanager_config(
            env_file=env_file,
            output_file=tmp_path / "alertmanager.yml",
        )


def test_production_renderer_requires_real_on_call_recipient(tmp_path):
    env_file = _write_env(
        tmp_path / ".env.production",
        ENVIRONMENT="production",
        ALERT_DEFAULT_WEBHOOK_URL="https://alerts.example.org/hooks/avinya",
        ALERT_EMAIL_TO="oncall@avinya-hms.local",
    )

    with pytest.raises(ValueError, match="valid on-call recipient"):
        render_alertmanager_config(
            env_file=env_file,
            output_file=tmp_path / "alertmanager.yml",
        )


def test_production_renderer_renders_explicit_external_receivers(tmp_path):
    env_file = _write_env(
        tmp_path / ".env.production",
        ENVIRONMENT="production",
        ALERT_DEFAULT_WEBHOOK_URL="https://alerts.example.org/hooks/avinya",
        ALERT_EMAIL_TO="oncall@example.org",
        SMTP_HOST="smtp.example.org",
        SMTP_PORT="587",
        SMTP_FROM="alerts@example.org",
    )
    output = tmp_path / "alertmanager.yml"

    result = render_alertmanager_config(env_file=env_file, output_file=output)

    rendered = result.read_text(encoding="utf-8")
    assert result == output
    assert 'smtp_smarthost: "smtp.example.org:587"' in rendered
    assert 'smtp_from: "alerts@example.org"' in rendered
    assert 'to: "oncall@example.org"' in rendered
    assert 'url: "https://alerts.example.org/hooks/avinya"' in rendered
    assert 'url: "https://alerts.example.org/hooks/avinya?severity=critical"' in rendered
    assert 'url: "https://alerts.example.org/hooks/avinya?severity=warning"' in rendered
    assert "${" not in rendered


def test_renderer_rejects_non_http_webhook_url(tmp_path):
    env_file = _write_env(
        tmp_path / ".env",
        ENVIRONMENT="development",
        ALERT_DEFAULT_WEBHOOK_URL="file:///tmp/alert-hook",
    )

    with pytest.raises(ValueError, match="Must have http or https"):
        render_alertmanager_config(
            env_file=env_file,
            output_file=tmp_path / "alertmanager.yml",
        )
