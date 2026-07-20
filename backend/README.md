# 🌊 Fisherman OS Backend — Phase 1 (Goa MVP)

The WhatsApp-bot backend from the [execution plan](../execution_plan.md) §2-§4:
a FastAPI service that serves fishermen in South Goa with a **3:30 AM morning
sea forecast**, **market prices from Goa landing centers**, and an **always-on
SOS distress flow** — in English, Konkani (Romi), Hindi and Marathi.

## What's implemented (execution plan → code)

| Plan item | Where |
|:---|:---|
| Backend (FastAPI + PostgreSQL/Supabase) | `app/main.py`, `app/database.py` (SQLite dev / Postgres prod via `DATABASE_URL`) |
| INCOIS/IMD data pipeline | `app/providers/weather/incois.py` (+ OpenWeatherMap fallback + deterministic synthetic provider) |
| Sea-safety classification 🟢🟡🔴 | `app/services/safety.py` (INCOIS/IMD small-craft thresholds) |
| Message composer (Konkani + English templates) | `app/bot/composer.py`, `app/localization/strings.py` (en/kok/hi/mr) |
| Scheduled 3:30 AM forecast push | `app/scheduler.py` (APScheduler, Asia/Kolkata) |
| Market price pipeline (field agents by 5 AM) | `app/services/price_service.py`, `POST /admin/prices`, WhatsApp `PRICE` command |
| Live per-fish market prices (FMPIS/NFDB, all Goa markets) | `app/providers/prices/fmpis.py`, ask-which-fish flow in `app/bot/router.py` |
| Price digest push at 5 AM + "💡 TIP" market-switch nudge | `app/scheduler.py`, `best_market_tip()` |
| SOS system (location sharing + ICG 1554 + contacts) | `app/services/sos_service.py`, 5-minute follow-up job |
| Onboarding via WhatsApp ("Hi" → name, village, boat) | `app/bot/router.py` state machine; first forecast sent immediately |
| Supabase schema (users, messages, prices, catches*) | `app/models.py` (*catch logging is Phase 2 by design) |
| WhatsApp Business API via Gupshup | `app/providers/whatsapp/gupshup.py` (+ console provider for dev) |
| KPI tracking (500 users, 60% DAU, SOS count, WTP) | `GET /admin/metrics`, `message_logs` table |

Out of scope for Phase 1 (per plan): fish-zone predictions, catch logging,
AI/ML, hardware, Android app.

## Quick start

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env          # defaults run fully offline (console + synthetic)
uvicorn app.main:app --reload
```

Then simulate a fisherman sending "Hi" the way Gupshup would:

```bash
curl -X POST localhost:8000/webhook/gupshup -H 'Content-Type: application/json' -d '{
  "type": "message",
  "payload": {"id": "m1", "type": "text", "source": "919822000001",
              "sender": {"phone": "919822000001", "name": "Rajesh"},
              "payload": {"text": "Hi"}}}'
```

With `WHATSAPP_PROVIDER=console` every outbound message is printed to the
server log, so you can walk the whole onboarding → forecast → prices → SOS
flow from curl.

### Tests

```bash
python -m pytest -q     # 78 tests: safety, composer, onboarding, commands, SOS, prices, scheduler, API
```

### Docker

```bash
docker compose up --build   # API on :8000 + Postgres 16
```

## Bot commands (WhatsApp)

| Message | Action |
|:---|:---|
| `Hi` (first contact) | Registration: language → name → village → boat type → first forecast |
| `1` | Detailed forecast (with source + issue time) |
| `2` / `PRICES` | Asks which fish, then live per-fish prices across all Goa markets (nearest first); `ALL` for the full digest |
| `SOS` | Emergency: alert created, contacts notified, 1554 surfaced, 5-min location loop |
| *share location* | Attached to the active SOS; contacts get the maps link |
| `CANCEL` | Deactivate SOS, stand down contacts |
| `CONTACT <name> <phone>` | Add an emergency contact |
| `VILLAGE <name>` | Change forecast village |
| `LANG` | Switch language (English / Konkani / हिंदी / मराठी) |
| `STOP` / `START` | Pause / resume daily pushes (SOS always stays active) |
| `HELP` | Command menu |
| `PRICE <center> <species> <₹/kg>` | Field agents only: submit a price (e.g. `PRICE Betul bangdo 85`) |
| *anything else* | LLM responder (see below) |

## LLM responder (Groq)

Messages that don't match a command above go to a Groq LLM
(`llama-3.3-70b-versatile` by default) that classifies intent and answers in
the user's language (English, Romi Konkani, Hindi, Marathi — it mirrors the
message language when it differs from the profile). One chat call returns
`{"intent", "reply"}`:

- **forecast / prices / help / stop / start / language** → routed to the same
  structured handlers as the keyword commands (`"aaj samudra kasa aahe?"`
  gets the real forecast template, not free-form prose).
- **emergency** — natural-language distress (`"majhi hod budte aahe"`) gets a
  localized confirmation with a **one-tap SOS button**; tapping it sends
  `SOS` through the normal keyword path. The LLM can never raise an alert
  itself.
- **answer** — relevant free-form questions, grounded ONLY in the live
  forecast + price data injected into the prompt (it is instructed never to
  invent numbers).
- **off_topic** — polite localized decline for anything unrelated.

Safeguards: the user message is passed as data with anti-injection rules,
intents are allowlisted, replies are length-clamped, there's a per-user
hourly rate limit (`LLM_RATE_LIMIT_PER_HOUR`), and any failure — key unset,
Groq down, timeout, malformed output — falls back to the static help reply,
so the bot never goes silent.

Setup: set `GROQ_API_KEY` in the environment (Vercel → Project → Settings →
Environment Variables). Never commit the key. Leave it empty to disable the
LLM path entirely.

## HTTP API

| Endpoint | Auth | Purpose |
|:---|:---|:---|
| `GET /health` | — | Liveness |
| `GET/POST /webhook/gupshup` | — | Gupshup callback URL |
| `POST /admin/prices` | `X-API-Key` | Bulk price entry (field ops tooling) |
| `GET /admin/prices?day=` | `X-API-Key` | Review recorded prices |
| `GET /admin/metrics` | `X-API-Key` | KPI dashboard (registered, DAU %, SOS, deliveries) |
| `GET /admin/sos` | `X-API-Key` | Active SOS alerts with last position |
| `POST /admin/sos/{id}/resolve` | `X-API-Key` | Close an alert after ICG follow-up |
| `POST /admin/broadcast` | `X-API-Key` | Announcement to all (or one village) |
| `POST /admin/users/{phone}/make-field-agent` | `X-API-Key` | Grant PRICE-command rights |
| `POST /admin/jobs/morning-push`, `/admin/jobs/price-push` | `X-API-Key` | Manual job triggers |

## Scheduled jobs (IST)

| Time | Job |
|:---|:---|
| 03:30 | Fresh forecast per village → push to every registered, subscribed user |
| 04:30 | FMPIS ingestion attempt (no-op until the NFDB API/MoU lands; field agents are the MVP source) |
| 05:00 | Price digest push |
| every 5 min | SOS follow-up: location nudge to the fisherman, position relay to contacts |

## Production checklist (deploy week)

1. **Supabase**: create the project, set `DATABASE_URL` (asyncpg URL). Tables
   are created on startup; introduce Alembic before running multiple instances.
2. **Gupshup**: register the WhatsApp Business number, set the webhook to
   `https://<host>/webhook/gupshup`, fill `GUPSHUP_*` env vars, and submit the
   morning-forecast/price/SOS templates for Meta approval (required for
   business-initiated 3:30 AM pushes; templates live in `app/localization/strings.py`).
3. **INCOIS**: confirm the district OSF feed URL (`INCOIS_RSS_URL`) from the
   INCOIS portal registration; the parser is defensive but the URL is
   deployment-config, not code.
4. **OpenWeatherMap** (optional fallback): set `OPENWEATHER_API_KEY`.
5. Set a strong `ADMIN_API_KEY`; put the API behind HTTPS (Railway/Render TLS).
6. **DPDP Act 2023**: location data is stored only for active SOS alerts;
   message logs hold operational data — review retention with counsel before
   scale-up.

## Konkani note

Konkani strings use the Romi (Latin) script common on WhatsApp among the
fishing communities of Salcete/Mormugao, drafted for the pilot and marked
for native-speaker review before the Meta template submission (the field
pilot in Betul is the review loop).
