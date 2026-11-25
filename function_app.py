import base64
import csv
import io
import json
import mimetypes
import os
from pathlib import Path
from datetime import datetime, timezone

import azure.functions as func
from azure.core.exceptions import ResourceModifiedError

from link_service import as_bool, generated_code, public_link, utc_now, validate_code, validate_url
from storage import LinkStore, PARTITION
from identity_policy import tenant_user

app = func.FunctionApp()
STATIC = Path(__file__).parent / "static"


def json_response(data, status=200):
    return func.HttpResponse(json.dumps(data, default=str), status_code=status, mimetype="application/json")


def error(message, status=400):
    return json_response({"error": message}, status)


def body(req):
    try:
        return req.get_json()
    except ValueError:
        raise ValueError("Request body must be valid JSON.")


def admin_identity(req):
    raw = req.headers.get("X-MS-CLIENT-PRINCIPAL")
    if not raw:
        return None
    try:
        claims = json.loads(base64.b64decode(raw)).get("claims", [])
    except (ValueError, json.JSONDecodeError):
        return None
    by_type = {}
    for claim in claims:
        by_type.setdefault(claim.get("typ", ""), []).append(claim.get("val", ""))
    oid = next(iter(by_type.get("http://schemas.microsoft.com/identity/claims/objectidentifier", [])), "")
    name = next(iter(by_type.get("name", []) + by_type.get("preferred_username", [])), oid)
    allowed_ids = {x.strip() for x in os.getenv("ADMIN_OBJECT_IDS", "").split(",") if x.strip()}
    allowed_roles = {x.strip() for x in os.getenv("ADMIN_APP_ROLES", "UrlShortener.Admin").split(",") if x.strip()}
    roles = set(by_type.get("roles", []))
    return name if oid in allowed_ids or roles & allowed_roles else None


def require_admin(req):
    if req.headers.get("Authorization"):
        return ""
    return tenant_user(req.headers.get("X-MS-CLIENT-PRINCIPAL"), os.getenv("ALLOWED_TENANT_ID", "")) or ""



def new_entity(code, payload, actor, source="native"):
    now = utc_now()
    return {
        "PartitionKey": PARTITION, "RowKey": code,
        "DestinationUrl": validate_url(payload.get("destinationUrl") or payload.get("url")),
        "Description": str(payload.get("description") or "").strip(),
        "IsActive": as_bool(payload.get("isActive"), True),
        "ExpiresOn": payload.get("expiresOn") or "",
        "CreatedOn": now, "CreatedBy": actor, "ModifiedOn": now, "ModifiedBy": actor,
        "ClickCount": 0, "HistoricalClickCount": int(payload.get("historicalClickCount") or 0),
        "LastClickedOn": "", "Source": source,
        "SourceDomain": str(payload.get("sourceDomain") or "").strip(),
        "Tags": str(payload.get("tags") or "").strip(),
    }


@app.route(route="api/shorten", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def shorten(req: func.HttpRequest):
    try:
        payload = body(req)
        actor = req.headers.get("X-PowerAutomate-Flow", "power-automate")
        alias = payload.get("alias")
        store = LinkStore()
        if alias:
            code = validate_code(alias)
            if not store.create(new_entity(code, payload, actor)):
                return error("That alias already exists and cannot be reassigned.", 409)
        else:
            for _ in range(10):
                code = generated_code()
                if store.create(new_entity(code, payload, actor)):
                    break
            else:
                return error("Could not allocate a unique code; retry the request.", 503)
        return json_response(public_link(store.get(code), os.environ["SHORTLINK_BASE_URL"]), 201)
    except ValueError as exc:
        return error(str(exc))


@app.route(route="api/links", methods=["GET", "POST"], auth_level=func.AuthLevel.ANONYMOUS)
def list_links(req):
    actor = require_admin(req)
    if not actor: return error("A permitted directory user must sign in.", 401)
    if req.method == "GET" and req.params.get("session") == "1":
        name = req.headers.get("X-MS-CLIENT-PRINCIPAL-NAME") or actor
        return func.HttpResponse(json.dumps({"name": name}), mimetype="application/json", headers={"Cache-Control": "no-store"})
    store = LinkStore()
    if req.method == "POST":
        try:
            payload = body(req); alias = payload.get("alias")
            if alias:
                code = validate_code(alias)
                if not store.create(new_entity(code, payload, actor)): return error("That alias already exists and cannot be reassigned.", 409)
            else:
                for _ in range(10):
                    code = generated_code()
                    if store.create(new_entity(code, payload, actor)): break
                else: return error("Could not allocate a unique code; retry the request.", 503)
            return json_response(public_link(store.get(code), os.environ["SHORTLINK_BASE_URL"]), 201)
        except ValueError as exc: return error(str(exc))
    return json_response({"items": [public_link(x, os.environ["SHORTLINK_BASE_URL"]) for x in store.list(req.params.get("search", ""))]})


@app.route(route="api/links/item/{*code}", methods=["GET", "PATCH"], auth_level=func.AuthLevel.ANONYMOUS)
def link_by_code(req):
    actor = require_admin(req)
    if not actor: return error("A permitted directory user must sign in.", 401)
    code = validate_code(req.route_params["code"])
    store = LinkStore(); entity = store.get(code)
    if not entity: return error("Link not found.", 404)
    if req.method == "GET": return json_response(public_link(entity, os.environ["SHORTLINK_BASE_URL"]))
    try:
        payload = body(req)
        # Intentionally never reads or changes RowKey: short codes are immutable.
        if "destinationUrl" in payload: entity["DestinationUrl"] = validate_url(payload["destinationUrl"])
        for key, column in (("description", "Description"), ("expiresOn", "ExpiresOn"), ("tags", "Tags")):
            if key in payload: entity[column] = str(payload[key] or "").strip()
        if "isActive" in payload: entity["IsActive"] = as_bool(payload["isActive"])
        entity["ModifiedOn"] = utc_now(); entity["ModifiedBy"] = actor
        store.update(entity)
        return json_response(public_link(store.get(code), os.environ["SHORTLINK_BASE_URL"]))
    except ValueError as exc: return error(str(exc))
    except ResourceModifiedError: return error("Link was updated by someone else; refresh and retry.", 409)


@app.route(route="api/links/import", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def import_csv(req):
    actor = require_admin(req)
    if not actor: return error("A permitted directory user must sign in.", 401)
    try:
        reader = csv.DictReader(io.StringIO(req.get_body().decode("utf-8-sig")))
        required = {"code", "destinationUrl"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames): return error("CSV requires code,destinationUrl columns.")
        store = LinkStore(); imported=[]; conflicts=[]; invalid=[]
        for line, row in enumerate(reader, start=2):
            try:
                code = validate_code(row["code"])
                item = new_entity(code, row, actor, row.get("source") or "rebrandly")
                item["CreatedOn"] = row.get("createdOn") or item["CreatedOn"]
                item["SourceDomain"] = row.get("sourceDomain") or row.get("domain") or ""
                if store.create(item): imported.append(code)
                else: conflicts.append({"line": line, "code": code})
            except (ValueError, TypeError) as exc: invalid.append({"line": line, "error": str(exc)})
        return json_response({"imported": imported, "conflicts": conflicts, "invalid": invalid}, 201)
    except UnicodeDecodeError: return error("CSV must be UTF-8 encoded.")


@app.route(route="api/links/export", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def export_csv(req):
    if not require_admin(req): return error("A permitted directory user must sign in.", 401)
    fields = ["code", "destinationUrl", "description", "isActive", "createdOn", "createdBy", "modifiedOn", "modifiedBy", "expiresOn", "clickCount", "historicalClickCount", "lastClickedOn", "source", "sourceDomain", "tags"]
    stream = io.StringIO(); writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader()
    for entity in LinkStore().list(limit=10000):
        link = public_link(entity, os.environ["SHORTLINK_BASE_URL"])
        writer.writerow({key: link.get(key, "") for key in fields})
    return func.HttpResponse(stream.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=short-links.csv"})


@app.route(route="manage/{asset?}", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def admin_site(req):
    # Easy Auth is intentionally checked by API routes. This page directs visitors to Entra sign-in.
    asset = req.route_params.get("asset") or "admin.html"
    if asset not in {"admin.html", "admin.css", "admin.js"}: return error("Not found.", 404)
    content_type = mimetypes.guess_type(asset)[0] or "application/octet-stream"
    return func.HttpResponse((STATIC / asset).read_bytes(), mimetype=content_type)


@app.route(route="{*code}", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def redirect(req):
    code = req.route_params["code"]
    # Reserve operational routes even when no Static Web Apps proxy is present.
    if code in {"api", "admin", "runtime", "manage", ".auth"}: return error("Not found.", 404)
    entity = LinkStore().get(code)
    if not entity or not entity.get("IsActive", True): return error("Link not found.", 404)
    expiry = entity.get("ExpiresOn")
    if expiry and datetime.fromisoformat(expiry.replace("Z", "+00:00")) <= datetime.now(timezone.utc): return error("This link has expired.", 410)
    LinkStore().increment_click(code, utc_now())
    return func.HttpResponse(status_code=302, headers={"Location": entity["DestinationUrl"], "Cache-Control": "no-store"})
