# Validation record

Checked on 2026-11-11 using clean Python virtual environments and `npm ci` in separate portfolio directories. No original virtual environment, database, upload or secret file was reused.

- Backend: 230 existing pytest cases passed, including the three PostgreSQL SQL-isolation cases, plus one added parser regression test passed separately.
- Frontend production build passed. Its large-bundle warning remains a performance improvement opportunity.
- Alembic migrations succeeded on a fresh SQLite demo and a disposable PostgreSQL validation database.
- Seed completed and a second execution preserved the records.
- Browser: Alex login and dashboard, synthetic PDF payroll import, explicit assistant-disabled status, logout and Sam login inspected. Sam's expense screen showed only the single Sam fixture, not Alex's entries.
- The GitHub Actions browser job runs the adapted end-to-end script on a fresh demo database. Its live status is available in Actions after publication.

The Python suite reports deprecation warnings from SQLAlchemy, Pydantic, FastAPI and PyPDF2. These are not hidden; dependency modernization remains future work. Live Gmail/WhatsApp calls, external provider credentials and local model inference were not exercised. OCR of scanned documents was not part of the supplied text-PDF demonstration.

## Privacy review

The public tree was reviewed with detect-secrets plus targeted checks for provider tokens, private keys, personal identifiers, original customer references and contact data. Findings were classified: isolated test passwords, a development-only fallback, UI labels and Alembic revision identifiers are not live credentials. Runtime secrets are generated locally and excluded from Git.

Only the newly generated screenshots and synthetic PDF (where present) are included as demonstration assets. Screenshots have no EXIF metadata; the PDF identifies itself as fictional. Open Sans font attribution is retained where bundled. No original binary document, financial report, dataset, client artwork, database or historical commit is part of these new repositories.

This review is not a penetration test or a security certification. Docker Compose configuration was prepared, but the local validation used native processes because the Docker engine was not running. The GitHub Actions jobs provide an independent clean-checkout validation after publication.

## Independent clean-checkout verification

GitHub Actions completed successfully on 2026-11-11 for code commit `08eeee11ed89113c7df53e914d2f9cdfc2ba21a7`: [view run](https://github.com/Rafael-T-Melo10/financaslm-demo/actions/runs/43116553568). Dependencies were installed from the repository in clean hosted runners.

All 231 backend tests, the production build and all 11 end-to-end browser scenarios passed. The browser suite includes the synthetic document import, login failure/recovery and mobile overflow checks. The initial mobile assistant overflow was corrected before this successful run.
