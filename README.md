# FARM360

FARM360 is a single-business agricultural services website and CRM built as a Flask modular monolith. It includes a database-backed public site, administrator content tools, a lead lifecycle, quote and payment records, automatic project creation, and a session-authenticated `/api/v1/` interface.

## Local setup

Use a supported Python 3.12+ installation and PostgreSQL. SQLite is convenient for local experiments but PostgreSQL is the intended deployment database.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` with a strong random `SECRET_KEY` and the development `DATABASE_URL`. Do not commit `.env`.

Initialize migrations once, inspect the generated revision, then apply it:

```powershell
$env:FLASK_APP = "run.py"
flask db init
flask db migrate -m "initial schema"
flask db upgrade
flask seed-services
flask create-admin
flask run
```

The initial Alembic revision is checked in. On a fresh database use `flask db upgrade` rather than `db.create_all()`. For later model changes, run `flask db migrate -m "describe change"`, review the generated revision, then apply with `flask db upgrade`. `/healthz` checks both process routing and database connectivity.

## Tests and quality checks

```powershell
pytest
ruff check .
```

Tests use isolated in-memory SQLite data. Before release, also exercise migrations and the complete enquiry-to-project flow against a disposable PostgreSQL database. Never point tests at production.

## Administrator and workflow

There is no public admin registration. Run `flask create-admin` interactively; passwords must be at least 12 characters and are hashed with Werkzeug. The browser and API use Flask-Login sessions, and state-changing browser requests require CSRF tokens.

Leads advance one stage at a time. Stage-specific details live in an audited JSON payload. Quotes use Decimal/Numeric amounts and revisions. Payments are recorded separately from verification; Closed Won requires approved scope and verified payments covering the full agreed amount. Won closure and project creation are one transaction, and the project has a unique lead relationship. Lost closure needs a reason and locks the lead.

The JSON API contract is exposed at `/api/v1/openapi.json`. Public endpoints expose active services, published portfolio entries, and enquiry submission. Admin routes require an authenticated session; browser deployments must retain CSRF protection. The API currently reuses the same lifecycle services as the HTML application.

## Images and content

Website content is editable in the admin area. Image uploads validate extension, content signature, and per-file size, and use random storage keys. Local development stores files under the Flask instance directory. Production uploads require S3-compatible storage configured with `UPLOAD_STORAGE_BACKEND=s3`, `UPLOAD_BUCKET`, `UPLOAD_REGION`, and `UPLOAD_PUBLIC_BASE_URL`; AWS credentials should come from the host's role/secret mechanism. Configure the bucket/CDN to serve these objects publicly without allowing public writes. Render's application filesystem is ephemeral, and local uploads are rejected when the app runs in production mode.

## Render and Neon deployment

1. Create a Neon PostgreSQL database and restrict credentials to the application.
2. Create the Render web service from the repository; use build command `pip install -r requirements.txt` and start command `gunicorn run:app`.
3. Set `SECRET_KEY`, `DATABASE_URL` (SQLAlchemy URL using `postgresql+psycopg://`), `FLASK_DEBUG=0`, `SESSION_COOKIE_SECURE=1`, `PUBLIC_BASE_URL`, and a persistent `RATELIMIT_STORAGE_URI` such as Redis for multi-process rate limiting. Configure the S3 storage variables before enabling image uploads.
4. Deploy the application, then run `flask db upgrade` as a release command or one-off shell command. Review migrations before applying them.
5. Run `flask seed-services` (repeatable), then `flask create-admin` from a secure one-off shell.
6. Verify `/healthz`, sign in, publish accurate company information, and submit a test enquiry. Exercise stage advancement, quote approval, payment record and verification, and Closed Won project creation.
7. Configure durable image storage and verify restoration from a backup before publishing images.
8. Connect the custom `.in` domain in Render, configure DNS as Render specifies, force HTTPS, and verify secure cookies.
9. Set up Neon backups/restore points and document a regular export to a separate protected location. Periodically test restore into a separate database before changing production.

Free hosting/database tiers can sleep, impose compute/storage limits, and provide different backup retention guarantees. Confirm current provider limits and pricing before launch; do not rely on free-tier persistence for customer records or uploaded images.

## Recovery

Take a database backup before schema or application changes. For recovery, create a clean database, restore the latest verified backup, apply only reviewed forward migrations, redeploy the last known-good application, and verify `/healthz` plus a read-only CRM spot check. Keep database credentials in the hosting secret store; rotate them after suspected exposure. Never use destructive migration commands against the production database.

## Future multi-tenant work

The app intentionally serves one FARM360 business. SaaS support would require organization and membership models, tenant-scoped ownership and queries, role-based permissions, organization settings, isolation tests, and subscription billing. Filtering records only in templates would not be sufficient.

## Current implementation limits

- Production image uploads require a configured S3-compatible bucket and public read/CDN URL; that infrastructure has not been provisioned or tested here.
- API auth is same-site session cookie based; cross-origin clients need a separately reviewed CSRF/CORS strategy.
- The CRM provides the core seven-stage workflow but still needs the complete service-specific data capture and advanced filters described in the implementation checklist.
- The current OpenAPI JSON lists the main operations but does not yet provide full schemas and examples for every request/response.
- Migrations were verified on SQLite. PostgreSQL/Neon behavior and Render deployment were not verified in this environment.
