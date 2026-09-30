# Security 5.0.0

Authentication uses HTTP-only cookies, rotating refresh sessions, CSRF checks and Argon2. `ADMIN` and `SUPER_ADMIN` share administrator capabilities; project, partner, warehouse, accounts and service restrictions remain separate. Every application-aware endpoint checks user application access and product/inquiry ownership server-side.

Invitation tokens use cryptographically secure random bytes and only SHA-256 hashes are stored. Tokens are single-use, expiring and revocable. No plaintext password is generated. When SMTP is unavailable the activation link is returned once; it must not be logged.

Media stays private. Downloads require authentication and application authorization. Filenames are normalized, actual image bytes are decoded, and paths are resolved beneath configured roots. Drive credentials and IDs are never returned as media URLs.

Before go-live, place secrets in the platform secret manager, enforce HTTPS, restrict database/Drive access, enable log redaction and alerting, test backup restoration, and perform an independent penetration/authorization review.
