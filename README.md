# Stripe Webhook POC (Flask)

A minimal, production-leaning Flask project that receives Stripe webhooks, verifies signatures, and upserts payment data with idempotency. Includes:
- App factory + blueprints
- SQLAlchemy models
- Flask-Migrate (Alembic) wiring
- Pytest with an idempotency test
- Local dev defaults (SQLite) and easy migration to Postgres

## Quick start (local)

1. **Python env**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. **Env vars**
Copy `.env.example` to `.env` and fill in your Stripe keys:
```bash
cp .env.example .env
# edit .env
```

3. **DB setup (SQLite)**
```bash
flask db init
flask db migrate -m "init"
flask db upgrade
```

4. **Run app**
```bash
# runs on http://127.0.0.1:5000
flask --app wsgi run
```

5. **Stripe CLI (local forwarding)**
```bash
stripe login
stripe listen --forward-to localhost:5000/webhooks/stripe
stripe trigger payment_intent.succeeded
```

6. **Run tests**
```bash
pytest -q
```

## Notes
- Idempotency: We store `stripe_event_id` uniquely in `payment_events`. Duplicate deliveries return 200 without double-writing business rows.
- Amounts are stored in **minor units** (cents).
- To link Orders and Payments, supply `metadata={"order_id": "<your-order-id>"}` when creating PaymentIntents / Checkout Sessions.
- For Postgres: set `SQLALCHEMY_DATABASE_URI` accordingly (e.g., `postgresql+psycopg://...`) and run migrations again.
