# FARM360 implementation checklist

## Architecture and data plan

- Modular Flask monolith: app factory, domain models, reusable lifecycle services, browser blueprints, and a versioned JSON API.
- PostgreSQL is authoritative; money uses `Numeric` and Python `Decimal`; critical won/lost operations are transactional and audit logged.
- Initial data model: administrator, service, portfolio item, singleton site settings, lead, lead activity, quote revision, payment, and one-to-one project.
- Authentication uses Flask-Login, CSRF-protected Flask-WTF forms, password hashing, and an explicit setup CLI. There is no public administrator registration.
- Initial release is single-business. Tenant support later requires organizations, memberships, tenant-scoped queries/authorization, and isolation tests.

## Progress

- [x] Phase 1: repository inspection; workspace was empty, with no existing app or `AGENTS.md`.
- [x] Phase 1: architecture, model plan, risks, and this checklist.
- [x] Phase 2: app factory, configuration, extensions, models, CLI seed/admin commands, and health route.
- [x] Phase 3: database-backed public pages, enquiry validation, CSRF, duplicate detection, and image rendering.
- [~] Phase 4: admin authentication, refreshed dashboard, searchable and filterable lead desk, project register, and seven-stage visual lead journey; richer filters and scheduling remain.
- [~] Phase 5: reusable lead lifecycle, quote revisions, payment verification, and audit events; the full service-specific field set and field-level stage validation remain to be completed.
- [x] Phase 6: transactional won closure with one-to-one project constraint.
- [~] Phase 7: versioned public/admin API with a basic OpenAPI contract; the contract and endpoint test coverage need expansion.
- [x] Phase 8: production configuration, security headers, and deployment/recovery guidance.
- [x] Phase 8: validated local development and S3-compatible production image storage adapters.
- [x] Phase 9: app route registration, 27 passing tests, Ruff checks, and fresh-schema migration checks.
- [x] Completed lead stages can be reviewed and edited; edits are recorded in the lead activity trail and approved scope remains protected.
- [x] Visual polish: responsive public homepage, updated type and color system, subtle scroll reveals, reduced-motion support, and a consistent admin workspace.
- [ ] Phase 9: PostgreSQL/Neon and Render verification.

## Risks and verification limits

- Automated tests pass against SQLite; a hosted PostgreSQL/Neon deployment was not available for verification.
- No PostgreSQL service or credentials are configured, so migrations against a real PostgreSQL database and hosted deployment cannot be verified here.
- Production S3 credentials, bucket policy, CDN URL, and hosted persistence have not been configured or verified.
- PostgreSQL and Neon were not available; only SQLite migration behavior was checked.
- The admin CRM captures a useful shared set of qualification, analysis, value, decision, and scope notes, but it does not yet expose every field listed for acreage, crops, water, challenges, deliverables, and ROI.
- Social-link editing, portfolio completion-date editing, and richer project scheduling fields remain incomplete.
- The OpenAPI document is intentionally basic at this stage and does not yet define full request/response schemas for every endpoint.
- Website copy and default service descriptions are operational descriptions only; no history, testimonials, awards, or performance claims are fabricated.
