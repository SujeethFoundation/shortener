# Azure Functions URL shortener

This is a Python Azure Functions app for `go.sujeeth.org`. It serves public redirects, a small Entra-backed administration site, Power Automate creation, and CSV import/export. Nothing in this folder deploys or changes Azure, DNS, GitHub, or Rebrandly by itself.

## Directory access

Set `ALLOWED_TENANT_ID` to your Microsoft Entra directory tenant ID before deployment. App Service Authentication must be enabled and its Microsoft identity provider configured; this app relies on its validated identity headers. Management access is available to signed-in users in that tenant, including guest users in the directory. Entra assignment and App Service authorization rules can further restrict access. A missing tenant setting denies management access. Power Automate continues to use its function-key endpoint.

## What is protected

| Route | Purpose | Access |
|---|---|---|
| `GET /{code}` | HTTP 302 public redirect | Public |
| `POST /api/shorten` | Power Automate creation | Function key |
| `/manage` | Management interface | Sign-in link; management calls require Entra admin |
| `GET/POST /api/links`, `PATCH /api/links/{code}` | Search, create, view, edit | Entra admin |
| `POST /api/links/import`, `GET /api/links/export` | CSV migration | Entra admin |

The short code is `RowKey`. Update code never accepts an alias or RowKey, and an existing alias returns HTTP 409. Disable a link instead of deleting it.

## Local setup

1. Install Python 3.11+ and Azure Functions Core Tools.
2. Create a virtual environment and install `pip install -r requirements.txt`.
3. Copy `local.settings.example.json` to `local.settings.json`. Set a development storage connection and a local base URL.
4. Run `func start` and open `http://localhost:7071/manage`.
5. Run `pytest` from this folder.

For local administration testing, Easy Auth headers do not exist. Deploy to an Entra-configured Function App before testing the management API.

## Azure deployment checklist

1. Review `infrastructure/main.bicep` and deploy it to a new resource group. Its storage key setting is a simple first deployment path; replace it with Key Vault or managed-identity connections before production.
2. In the Function App, enable system-assigned managed identity. Grant it **Storage Table Data Contributor** on the storage account if using `TABLES_ACCOUNT_URL`; then set `TABLES_ACCOUNT_URL=https://<account>.table.core.windows.net` and remove the account-key storage setting.
3. Configure App Service Authentication with Microsoft Entra ID. Set unauthenticated requests to **Allow anonymous** so redirects remain public. The admin API validates the Easy Auth principal plus `ADMIN_OBJECT_IDS` or the `UrlShortener.Admin` application role.
4. Deploy this folder with your preferred Azure Functions deployment method. Set `SHORTLINK_BASE_URL=https://go.sujeeth.org` only after the custom domain is ready.
5. Add the custom domain and certificate, then test staging redirects. Do not switch DNS until the migration comparison is clear.
6. Retrieve the `shorten` function key from Azure. In Power Automate, call `POST https://<app>/api/shorten` with `x-functions-key`; import `connector/openapi.json` to make a custom connector if preferred.

## Power Automate request

```json
{
  "destinationUrl": "https://sujeeth.org/circle",
  "alias": "career-circle",
  "description": "Career Circle information"
}
```

Send it as JSON with `x-functions-key`. `alias` is optional. A `201` response returns `shortUrl`, `code`, and the link fields.

## Migration

Use [migration/MIGRATION-REPORT.md](migration/MIGRATION-REPORT.md) and the CSV template. The importer preserves aliases and maps `historicalClickCount` separately from `clickCount`, which begins at zero in Azure. It reports conflicting aliases and invalid rows without overwriting existing links.

Sign in at `/manage`, choose the prepared UTF-8 CSV under **Import links**, and select **Import links**. The page lists skipped rows and their reasons. Import happens row by row; if a request is interrupted, check the list and retry the same file. Existing aliases are skipped.

The current migration data is empty because the open Chrome window did not contain Rebrandly. Export Rebrandly links as CSV and import only after the row-by-row verification steps in the report.

## Platform architecture

This repo is one of nine in the SujeethFoundation org. The architecture docs live in the website repo's `architecture/` folder: [platform architecture](https://github.com/SujeethFoundation/sujeethfoundation.github.io/blob/main/architecture/platform-architecture.md), [data model and portal](https://github.com/SujeethFoundation/sujeethfoundation.github.io/blob/main/architecture/platform-data-model-and-portal.md) and [business architecture](https://github.com/SujeethFoundation/sujeethfoundation.github.io/blob/main/architecture/business-architecture.md). This repo is the go.sujeeth.org link shortener. See "shortner" in the platform architecture doc. Each repo's README is listed in the platform architecture doc under "Repo READMEs".
