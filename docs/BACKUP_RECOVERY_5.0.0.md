# Backup and Recovery

Back up PostgreSQL daily with encrypted, versioned retention and test a restore quarterly. The database backup is authoritative for Drive file IDs, hierarchy, checksums and commercial history. Back up the dedicated Drive account using an approved organizational retention/export policy. Keep database and Drive snapshots from a consistent maintenance window when possible.

Recovery order: restore PostgreSQL, restore/re-authorize the Drive account, verify OAuth secrets, run `alembic upgrade head`, run `reconcile_media.py`, then validate protected media and PDFs with a least-privilege customer account and an administrator account. Never regenerate commercial IDs or silently replace missing images; PDFs use a controlled placeholder until media is restored.
