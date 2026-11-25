"""Validation and representation helpers with no Azure dependency."""
from __future__ import annotations

import re
import secrets
from datetime import datetime, timezone
from urllib.parse import urlparse

CODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*(?:/[A-Za-z0-9][A-Za-z0-9_-]*)*$")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_code(code: str) -> str:
    code = (code or "").strip()
    if len(code) > 128 or not CODE_RE.fullmatch(code) or code.split('/')[0].lower() in {'api', 'admin', '.auth'}:
        raise ValueError("Alias must use letters, numbers, hyphens, underscores, and optional path separators.")
    return code


def validate_url(value: str) -> str:
    value = (value or "").strip()
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Destination URL must be an absolute http or https URL.")
    return value


def generated_code() -> str:
    return secrets.token_urlsafe(6).replace("-", "a").replace("_", "b")[:8]


def as_bool(value, default=True) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    if str(value).lower() in {"true", "1", "yes"}:
        return True
    if str(value).lower() in {"false", "0", "no"}:
        return False
    raise ValueError("isActive must be true or false.")


def public_link(entity: dict, base_url: str) -> dict:
    code = entity.get("Code", entity["RowKey"])
    return {
        "code": code,
        "shortUrl": f"{base_url.rstrip('/')}/{code}",
        "destinationUrl": entity["DestinationUrl"],
        "description": entity.get("Description", ""),
        "isActive": bool(entity.get("IsActive", True)),
        "createdOn": entity.get("CreatedOn"),
        "createdBy": entity.get("CreatedBy", ""),
        "modifiedOn": entity.get("ModifiedOn"),
        "modifiedBy": entity.get("ModifiedBy", ""),
        "expiresOn": entity.get("ExpiresOn") or None,
        "clickCount": int(entity.get("ClickCount", 0)),
        "historicalClickCount": int(entity.get("HistoricalClickCount", 0)),
        "lastClickedOn": entity.get("LastClickedOn") or None,
        "source": entity.get("Source", "native"),
        "sourceDomain": entity.get("SourceDomain", ""),
        "tags": entity.get("Tags", ""),
    }
