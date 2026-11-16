# Nexora Server

Backend API for **Nexora**, a PySide6 (Qt) desktop application (system monitor / booster / game launcher). This service is purpose-built to serve that desktop client — authentication, user profiles, subscriptions, and device management — and is not a generic auth server.

Tech stack: Python 3.13, FastAPI, PostgreSQL, SQLAlchemy 2.0 (async ORM), Alembic, asyncpg, Pydantic v2, `bcrypt`, `PyJWT`, `aiosmtplib`, slowapi (rate limiting), Docker.

## Project layout

```
app/
  main.py                # app factory, lifespan, router includes, CORS, exception handlers
  core/                  # settings, security (hashing/JWT/codes), logging, rate limiting
  db/                    # SQLAlchemy declarative base + async session/engine
  models/                # ORM models (User, Subscription, Device, RefreshToken, VerificationCode)
  schemas/                # Pydantic v2 request/response schemas
  repositories/           # data-access layer (one per aggregate)
  services/               # business logic, orchestrates repositories
  api/v1/                 # routers: auth, users, subscriptions, devices, health, payments, launcher
  exceptions.py           # custom exceptions + global exception handlers
alembic/                  # async-compatible migrations
tests/                    # smoke tests + security unit tests
```

## Local development (without Docker)

Requirements: Python 3.13, a running PostgreSQL 16 instance.

```bash
# 1. Create and activate a virtualenv
python3.13 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies (including dev/test extras)
pip install -e ".[dev]"

# 3. Configure environment
cp .env.example .env
# edit .env — at minimum set DATABASE_URL and JWT_SECRET_KEY

# 4. Create the database (adjust to your local Postgres setup)
createuser boostx --pwprompt   # if it doesn't exist yet
createdb boostx --owner boostx

# 5. Run migrations
alembic upgrade head

# 6. Run the dev server
uvicorn app.main:app --reload
```

The API is now available at `http://localhost:8000/api/v1`, with interactive docs at `http://localhost:8000/docs`.

### Running tests

```bash
pytest
```

This runs the app-import smoke tests and unit tests for `app/core/security.py` (password hashing, JWT round-trip, refresh token hashing, verification codes). It does not require a database connection.

### Creating new migrations

After changing a model in `app/models/`:

```bash
alembic revision --autogenerate -m "describe the change"
# review the generated file in alembic/versions/ before applying
alembic upgrade head
```

Note: Postgres ENUM types (`subscription_plan`, `subscription_status`, `verification_purpose`) are not dropped automatically by Alembic autogenerate when a downgrade drops their table — the initial migration handles this explicitly. Keep that in mind if you add new enum columns.

## Running with Docker

Requirements: Docker + Docker Compose.

```bash
cp .env.example .env
# edit .env as needed — DATABASE_URL is overridden by docker-compose to point
# at the `db` service, but JWT_SECRET_KEY, SMTP_*, etc. still come from here.

docker compose up --build
```

This starts:
- `db` — PostgreSQL 16 with a healthcheck, data persisted in the `boostx_postgres_data` volume.
- `app` — the FastAPI app, built via the multi-stage `Dockerfile`. On startup it runs `alembic upgrade head` before starting `uvicorn`.

The API is available at `http://localhost:8000/api/v1`.

## Configuration

All configuration is environment-driven (see `.env.example` for the full list with comments). Key variables:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | asyncpg-driver Postgres URL |
| `JWT_SECRET_KEY` / `JWT_ALGORITHM` | JWT signing |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` / `REFRESH_TOKEN_EXPIRE_DAYS_REMEMBER_ME` | refresh token lifetime (normal vs. "remember me") |
| `VERIFICATION_CODE_EXPIRE_MINUTES` | 6-digit code TTL |
| `EMAIL_BACKEND` | `console` (logs codes instead of sending — good for local dev) or `smtp` |
| `SMTP_*` | SMTP credentials, used when `EMAIL_BACKEND=smtp` |
| `CORS_ORIGINS` | comma-separated allowed origins, or `*` (dev only — lock this down in production) |
| `MAX_DEVICES_PER_USER` | device registration cap per account, `0` = unlimited |
| `RATE_LIMIT_STORAGE_URI` | empty = in-memory rate limiting; set to a Redis URI to share limits across instances |
| `RELAY_SERVERS` | JSON list of relay servers handed to clients (see "Relay servers" below) |
| `RELAY_TOKEN_SECRET` | secret shared with every relay, used to sign client tokens — **environment only, never commit** |
| `RELAY_TOKEN_TTL_SECONDS` | lifetime of a relay token |
| `DEBUG` | when `false`, unhandled exceptions never leak details to clients |

**Production notes:**
- Set `CORS_ORIGINS` to an explicit list of trusted origins (wildcard `*` disables credentialed CORS requests anyway, per spec).
- Set `DEBUG=false`.
- Use a long, random `JWT_SECRET_KEY` (e.g. `openssl rand -hex 32`).
- Point `RATE_LIMIT_STORAGE_URI` at Redis if running multiple app instances/workers, so rate limits are shared rather than per-process.

## Relay servers

Game traffic is routed by `nexora-relay`, a small standalone program that runs on each VPS (source: `nexora-core/` in the client repository; a Linux x86-64 build is in `deploy/relay/`). This backend does not proxy any traffic itself — it only tells a signed-in client which relays exist and signs a token they accept. Relays never call back here and keep no user data, so adding a server needs no database change.

**Adding a relay**

```sh
# on the new VPS (needs iptables; UDP port 4700 must be open)
sudo install -m 755 deploy/relay/nexora-relay /usr/local/bin/
sudo mkdir -p /etc/nexora
sudo nexora-relay init -out /etc/nexora/relay.json      # prints the relay's public key
sudo cp deploy/relay/nexora-relay.service /etc/systemd/system/
sudo systemctl enable --now nexora-relay
```

- **First relay:** copy `token_secret` from its `/etc/nexora/relay.json` into this backend's `RELAY_TOKEN_SECRET`.
- **Every further relay:** before starting it, replace `token_secret` in its `relay.json` with that same value, so one token works on all of them. (`private_key` stays unique per relay.)
- Add the relay to `RELAY_SERVERS` and restart the backend:

```
RELAY_SERVERS=[{"id":"fra1","name":"Frankfurt","region":"EU","address":"203.0.113.10:4700","public_key":"<printed by init>"}]
```

`relay.json` and `RELAY_TOKEN_SECRET` are secrets: keep them on the servers only.

## API reference

Base path: `/api/v1`. Endpoints marked "auth" require an `Authorization: Bearer <access_token>` header.

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/register` | — | Register a new account; sends an email-verification code |
| POST | `/auth/login` | — | Log in, upserts the device, returns access + refresh tokens |
| POST | `/auth/logout` | yes | Revoke a specific refresh token |
| POST | `/auth/refresh` | — | Rotate a refresh token (reuse triggers full session revocation) |
| POST | `/auth/verify-email` | — | Confirm email with a 6-digit code |
| POST | `/auth/resend-verification` | — | Resend the email-verification code (rate-limited) |
| POST | `/auth/password-reset/request` | — | Request a password-reset code (rate-limited, anti-enumeration) |
| POST | `/auth/password-reset/confirm` | — | Reset password with a code; revokes all refresh tokens |
| POST | `/auth/change-password` | yes | Change password (requires current password) |
| POST | `/auth/change-email/request` | yes | Request an email change; code sent to the new address (rate-limited) |
| POST | `/auth/change-email/confirm` | yes | Confirm the pending email change |
| GET | `/users/me` | yes | Current user's profile |
| PATCH | `/users/me` | yes | Update `username` and/or `avatar_url` |
| GET | `/subscriptions/me` | yes | Current user's subscription (plan/status/period) |
| GET | `/devices` | yes | List the current user's registered devices |
| POST | `/devices/register` | yes | Register/update a device (enforces `MAX_DEVICES_PER_USER`) |
| DELETE | `/devices/{device_id}` | yes | Remove a device and revoke its refresh tokens |
| POST | `/relay/session` | yes | Relay list plus a signed token for the calling device (`{"device_id"}`); 503 until relays are configured |
| GET | `/health` | — | Liveness check, no DB hit |
| GET | `/health/db` | — | Readiness check, runs `SELECT 1` against the database |
| POST | `/payments/webhook/lava` | — | Stub — returns 501, reserved for a future Lava integration |
| GET | `/launcher/catalog` | — | Stub — returns 501, reserved for a future remote catalog feature |

Full interactive schema (request/response bodies, status codes) is available at `/docs` (Swagger UI) or `/redoc` once the app is running.

## Security notes

- Passwords are hashed with `bcrypt` (via the `bcrypt` package directly) — never stored or logged in plaintext.
- Refresh tokens are opaque random strings (`secrets.token_urlsafe`); only their SHA-256 hash is stored. The raw token is returned to the client exactly once, at issuance.
- Refresh tokens rotate on every `/auth/refresh` call. Presenting an already-rotated (revoked) token is treated as a compromise signal: all of that user's active refresh tokens are revoked immediately.
- 6-digit verification codes are generated with `secrets.randbelow`, hashed (SHA-256) before storage, and expire after `VERIFICATION_CODE_EXPIRE_MINUTES`.
- Sensitive auth endpoints (register, login, resend-verification, password-reset/request, change-email/request) are rate-limited per IP via slowapi.
- Response schemas are explicit Pydantic models everywhere, so internal fields (`password_hash`, `token_hash`, `code_hash`) can never leak in API responses.
- When `DEBUG=false`, unhandled exceptions return a generic `{"detail": "Internal server error"}` — the real error is logged server-side only.
