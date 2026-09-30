# Security notes

- Never deploy with demo users or the example secret key.
- Production startup refuses weak/default `SECRET_KEY` values and refuses `SEED_DEMO_DATA=true`.
- Authentication uses HttpOnly access/refresh cookies. The refresh token is opaque, stored as a SHA-256 hash in the database, rotated on refresh and revoked on logout.
- Unsafe requests require a matching double-submit CSRF token.
- Passwords use Argon2.
- Authorization is enforced in backend endpoints; frontend visibility is not treated as a security boundary.
- Commercial totals, stock transitions and document conversions are validated on the server.
- Use HTTPS and `COOKIE_SECURE=true` in production.
- Use managed PostgreSQL encryption/backups and provider secret storage.
- Add external rate limiting/WAF rules for login and sensitive endpoints at the platform edge for internet-facing deployments.
- Before enabling arbitrary document uploads, use object storage, MIME/size allowlists and malware scanning. The delivered v1 intentionally does not expose unsafe generic upload endpoints.
