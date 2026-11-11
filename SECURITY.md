# Demo security scope

This repository is intended for local portfolio evaluation with synthetic data. Keep `.env`, database files, uploads, tokens and logs out of Git. The configuration generator creates fresh local secrets; example values are not credentials.

The demo seed requires explicit portfolio mode and a database name containing `portfolio`. It refuses unrelated existing users. Never point it at a production database. Docker ports are bound to loopback and volumes use a separate project name.

If reporting a vulnerability, do not include a real secret or personal record in a public issue. Supply a minimal synthetic reproduction. Automated tests and secret scanning reduce risk but are not a security certification.
