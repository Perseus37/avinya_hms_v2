"""
Test suite verifying remediation of findings from Sections 26 & 27:
- N-91: Redis service container user configuration under dropped capabilities
- N-90: Real email alerting receivers and refusal of dummy webhook in production
- N-93: World-readable permissions (chmod 644) on Prometheus textfile metrics
- N-94: Idempotent foreign key index migrations (if_not_exists) and invalid index repair
- N-95: Textfile collector directory environment variable consistency
"""

import os
from pathlib import Path
import pytest
import yaml

from backend.scripts.render_alertmanager_config import render_alertmanager_config


def test_n91_redis_container_user_and_service_capabilities():
    """
    N-91: Redis must run with user: '999:1000' so that it does not attempt root writes
    to /data under cap_drop: [ALL]. docker-proxy has tmpfs /run, and clamav retains SETUID/SETGID.
    """
    compose_path = Path("docker-compose.prod.yml")
    assert compose_path.is_file()
    compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))

    redis_svc = compose["services"]["redis"]
    assert redis_svc.get("user") == "999:1000", "Redis service must specify user: '999:1000'"
    assert redis_svc.get("cap_drop") == ["ALL"], "Redis must drop all capabilities"

    # docker-proxy tmpfs for read_only container filesystem
    proxy_svc = compose["services"]["docker-proxy"]
    assert "/run" in proxy_svc.get("tmpfs", []), "docker-proxy must have /run tmpfs mount"

    # clamav SETUID/SETGID capability preservation
    clamav_svc = compose["services"]["clamav"]
    assert "SETUID" in clamav_svc.get("cap_add", [])
    assert "SETGID" in clamav_svc.get("cap_add", [])


def test_n90_alertmanager_email_delivery_and_production_guard(tmp_path):
    """
    N-90: Alertmanager must configure email_configs across all receivers so SMTP settings
    actually deliver alerts, and render_alertmanager_config must reject dummy webhook in production.
    """
    am_path = Path("deployments/alertmanager.yml")
    assert am_path.is_file()
    am_data = yaml.safe_load(am_path.read_text(encoding="utf-8"))

    # Receivers must have valid email_configs
    receivers = am_data.get("receivers", [])
    assert len(receivers) >= 3
    for recv in receivers:
        assert "email_configs" in recv, f"Receiver {recv.get('name')} must have email_configs"
        assert len(recv["email_configs"]) > 0
        to_addr = recv["email_configs"][0].get("to")
        assert to_addr and "@" in to_addr

    # Production guard: when ENVIRONMENT=production, dummy ingress webhook must raise ValueError
    prod_env = tmp_path / "prod.env"
    prod_env.write_text("ENVIRONMENT=production\n", encoding="utf-8")
    out_file = tmp_path / "am.out.yml"
    with pytest.raises(ValueError, match="Production Alertmanager cannot use circular dummy webhook"):
        render_alertmanager_config(env_file=prod_env, output_file=out_file)

    # Valid external webhook in production succeeds
    valid_prod_env = tmp_path / "valid_prod.env"
    valid_prod_env.write_text(
        "ENVIRONMENT=production\n"
        "ALERT_DEFAULT_WEBHOOK_URL=https://alerts.hospital.org/webhook\n"
        "ALERT_EMAIL_TO=emergency-oncall@hospital.org\n",
        encoding="utf-8",
    )
    render_alertmanager_config(env_file=valid_prod_env, output_file=out_file)
    valid_data = yaml.safe_load(out_file.read_text(encoding="utf-8"))
    assert valid_data["receivers"][0]["email_configs"][0]["to"] == "emergency-oncall@hospital.org"
    assert valid_data["receivers"][0]["webhook_configs"][0]["url"] == "https://alerts.hospital.org/webhook"


def test_n93_n95_backup_metrics_chmod_and_variable_consistency():
    """
    N-93 & N-95:
    - backup-postgres.sh must apply chmod 644 to metric files so user 65534 (node-exporter) can read them.
    - Script and compose must support both NODE_EXPORTER_TEXTFILE_DIR and NODE_EXPORTER_TEXTFILE_HOST_PATH.
    """
    backup_sh = Path("deployments/backup-postgres.sh").read_text(encoding="utf-8")

    # chmod 644 must be present for both status and success files
    assert 'chmod 644 "$textfile_dir/backup_postgres_status.prom"' in backup_sh
    assert 'chmod 644 "$textfile_dir/backup_postgres_last_success.prom"' in backup_sh

    # Both variable names must be handled
    assert "NODE_EXPORTER_TEXTFILE_DIR" in backup_sh
    assert "NODE_EXPORTER_TEXTFILE_HOST_PATH" in backup_sh

    # Check .env.example
    env_example = Path(".env.example").read_text(encoding="utf-8")
    assert "NODE_EXPORTER_TEXTFILE_HOST_PATH=" in env_example
    assert "NODE_EXPORTER_TEXTFILE_DIR=" in env_example


def test_n94_index_builder_handles_invalid_indexes_and_idempotent_migration():
    """
    N-94:
    - Alembic migration e1a3c7b5d902 must specify if_not_exists=True on all create_index calls.
    - build_indexes_concurrently.py must query indisvalid to detect broken indexes.
    """
    migration_path = Path("backend/alembic/versions/e1a3c7b5d902_complete_foreign_key_indexes.py")
    assert migration_path.is_file()
    migration_text = migration_path.read_text(encoding="utf-8")

    # All 134 create_index calls must have if_not_exists=True
    create_calls = [l for l in migration_text.splitlines() if "op.create_index(" in l]
    assert len(create_calls) == 134
    for call in create_calls:
        assert "if_not_exists=True" in call

    # build_indexes_concurrently.py must query indisvalid
    builder_text = Path("backend/scripts/build_indexes_concurrently.py").read_text(encoding="utf-8")
    assert "indisvalid" in builder_text
    assert "DROP INDEX CONCURRENTLY IF EXISTS" in builder_text
    assert "get_invalid_postgres_indexes" in builder_text

