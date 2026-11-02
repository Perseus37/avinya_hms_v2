"""Safely identify and optionally remove orphaned tenant branding assets.

The command is dry-run by default. It only considers files inside a tenant's
branding-assets directory whose names match the upload endpoint's server-side
asset ID format. Unknown files, symlinks, malformed tenant branding JSON, and
recent files are never removed.
"""

import argparse
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import re
import sys
from typing import Iterable

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_REPO_DIR = _BACKEND_DIR.parent
if str(_REPO_DIR) not in sys.path:
    sys.path.insert(0, str(_REPO_DIR))

from sqlalchemy import select

from backend.core.config import settings
from backend.core.database import ControlSessionLocal
from backend.control_plane.models import TenantRegistry

logger = logging.getLogger("avinya.brand_asset_reconciliation")

_TENANT_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
_ASSET_ID = re.compile(r"^[0-9a-f]{32}\.(?:png|jpg|jpeg|webp)$")
_TEMP_ID = re.compile(r"^\.[0-9a-f]{32}\.(?:png|jpg|jpeg|webp)\.part$")
_BRAND_ASSET_URL_PREFIX = "/api/ui/tenant-branding/assets/"
_MIN_GRACE_HOURS = 24


def _referenced_asset_ids(branding_json: str | None) -> set[str] | None:
    """Return local asset IDs; None means config is malformed and must be skipped."""
    if not branding_json:
        return set()
    try:
        branding = json.loads(branding_json)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(branding, dict):
        return None

    referenced: set[str] = set()
    for key in ("logo_url", "favicon_url"):
        value = branding.get(key)
        if not isinstance(value, str) or not value.startswith(_BRAND_ASSET_URL_PREFIX):
            continue
        asset_id = value[len(_BRAND_ASSET_URL_PREFIX):]
        if _ASSET_ID.fullmatch(asset_id):
            referenced.add(asset_id)
    return referenced


def reconcile_branding_assets(
    storage_root: Path | str,
    tenants: Iterable[object],
    *,
    grace_hours: float = 24,
    execute: bool = False,
    now: datetime | None = None,
    tenant_filter: str | None = None,
) -> dict:
    """Scan known tenant directories; execute=False reports without deleting."""
    if grace_hours < _MIN_GRACE_HOURS:
        raise ValueError("grace_hours must be at least 24 to protect in-flight uploads")
    root = Path(storage_root)
    if root.is_symlink():
        raise ValueError("Attachment storage root must not be a symlink")
    root = root.resolve()
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"Attachment storage directory is unavailable: {root}")

    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    cutoff = current_time.timestamp() - grace_hours * 3600

    tenant_rows = list(tenants)
    known_slugs = {
        getattr(tenant, "subdomain_slug", None)
        for tenant in tenant_rows
        if isinstance(getattr(tenant, "subdomain_slug", None), str)
    }
    if tenant_filter and tenant_filter not in known_slugs:
        raise ValueError(f"Unknown tenant slug: {tenant_filter}")

    result = {"dry_run": not execute, "candidates": [], "deleted": [], "skipped_tenants": []}
    for tenant in tenant_rows:
        slug = getattr(tenant, "subdomain_slug", None)
        if tenant_filter and slug != tenant_filter:
            continue
        if not isinstance(slug, str) or not _TENANT_SLUG.fullmatch(slug):
            result["skipped_tenants"].append({"tenant": str(slug), "reason": "invalid tenant slug"})
            continue

        references = _referenced_asset_ids(getattr(tenant, "ui_branding_json", None))
        if references is None:
            result["skipped_tenants"].append({"tenant": slug, "reason": "malformed branding configuration"})
            continue

        tenant_dir = root / slug
        if tenant_dir.is_symlink() or not tenant_dir.is_dir():
            continue
        try:
            tenant_dir.resolve().relative_to(root)
        except ValueError:
            result["skipped_tenants"].append({"tenant": slug, "reason": "tenant path escapes storage root"})
            continue

        asset_dir = tenant_dir / "branding-assets"
        if asset_dir.is_symlink() or not asset_dir.is_dir():
            continue
        try:
            asset_dir.resolve().relative_to(tenant_dir.resolve())
        except ValueError:
            result["skipped_tenants"].append({"tenant": slug, "reason": "branding path escapes tenant directory"})
            continue

        try:
            entries = list(os.scandir(asset_dir))
        except OSError as exc:
            result["skipped_tenants"].append({"tenant": slug, "reason": f"directory unavailable: {exc}"})
            continue

        for entry in entries:
            name = entry.name
            is_asset = bool(_ASSET_ID.fullmatch(name))
            is_stale_temp = bool(_TEMP_ID.fullmatch(name))
            if not (is_asset or is_stale_temp):
                continue
            if entry.is_symlink() or not entry.is_file(follow_symlinks=False):
                continue
            if is_asset and name in references:
                continue
            try:
                modified_at = entry.stat(follow_symlinks=False).st_mtime
            except OSError:
                continue
            if modified_at > cutoff:
                continue

            candidate = {
                "tenant": slug,
                "file": name,
                "kind": "orphaned_asset" if is_asset else "stale_temporary_upload",
            }
            result["candidates"].append(candidate)
            if execute:
                try:
                    # unlink removes a replaced symlink itself rather than following it;
                    # the no-symlink check above is retained as a conservative guard.
                    (asset_dir / name).unlink()
                    result["deleted"].append(candidate)
                except OSError as exc:
                    logger.warning("Could not remove %s/%s: %s", slug, name, exc)

    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Dry-run or remove stale, unreferenced tenant branding assets."
    )
    parser.add_argument("--tenant", help="Limit scanning to one known tenant slug.")
    parser.add_argument(
        "--grace-hours",
        type=float,
        default=24,
        help="Minimum file age before cleanup (minimum and default: 24 hours).",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually unlink eligible files. Without this flag the command is read-only.",
    )
    args = parser.parse_args(argv)
    if args.grace_hours < _MIN_GRACE_HOURS:
        parser.error("--grace-hours must be at least 24 to protect in-flight uploads")

    try:
        with ControlSessionLocal() as control_db:
            tenants = control_db.execute(select(TenantRegistry)).scalars().all()
            result = reconcile_branding_assets(
                settings.ATTACHMENTS_STORAGE_DIR,
                tenants,
                grace_hours=args.grace_hours,
                execute=args.execute,
                tenant_filter=args.tenant,
            )
    except (OSError, ValueError) as exc:
        logger.error("Branding asset reconciliation aborted: %s", exc)
        return 2

    mode = "EXECUTE" if args.execute else "DRY-RUN"
    print(
        f"{mode}: {len(result['candidates'])} eligible file(s); "
        f"{len(result['deleted'])} deleted; "
        f"{len(result['skipped_tenants'])} tenant(s) skipped."
    )
    for item in result["candidates"]:
        print(f"{'DELETED' if args.execute and item in result['deleted'] else 'WOULD DELETE'} "
              f"{item['tenant']}/{item['file']} [{item['kind']}]")
    for item in result["skipped_tenants"]:
        print(f"SKIPPED {item['tenant']}: {item['reason']}")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    raise SystemExit(main())
