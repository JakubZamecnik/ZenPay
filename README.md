# ZenPay Fintech API

REST API pro vytváření plateb s **idempotencí** a **transactional outbox** vzorem. Platby se ukládají do PostgreSQL; události se asynchronně publikují do RabbitMQ přes samostatný worker.

## Struktura projektu

```
ZenPay (Fintech API)/
├── README.md
├── requirements.txt          # Python závislosti
├── Dockerfile                # Image pro API a worker
├── docker-compose.yml        # Postgres, RabbitMQ, API, worker
├── .env                      # Lokální konfigurace (není v gitu)
├── .gitignore
├── app/
│   ├── main.py               # FastAPI aplikace, lifespan, /health
│   ├── config.py             # Nastavení z env (.env)
│   ├── worker.py             # Outbox relay → RabbitMQ + úklid idempotence
│   ├── api/
│   │   └── v1/
│   │       └── payments.py   # POST /payments
│   ├── db/
│   │   └── session.py        # Async engine a DB session
│   ├── models/
│   │   └── payment_models.py # Payment, IdempotencyKey, Outbox
│   └── schemas/
│       └── payment_schemas.py # Pydantic vstupy (PaymentCreate)
└── tests/
    └── test_payments.py      # Test idempotence platby
```

## Co kde je

| Soubor / složka | Účel |
|-----------------|------|
| `app/main.py` | Vstupní bod API, vytvoření tabulek při startu, health check |
| `app/api/v1/payments.py` | Endpoint pro vytvoření platby, idempotence, zápis do outboxu |
| `app/models/payment_models.py` | SQLModel tabulky v databázi |
| `app/schemas/payment_schemas.py` | Validace request body |
| `app/db/session.py` | Připojení k PostgreSQL (asyncpg) |
| `app/config.py` | `DATABASE_URL`, `RABBITMQ_URL` z prostředí |
| `app/worker.py` | Čte nezpracované záznamy z outboxu, posílá do fronty `payment_events` |
| `docker-compose.yml` | Celý stack: DB, fronta, API, worker |
| `tests/` | Pytest testy |

## Architektura

1. Klient pošle `POST /payments` s hlavičkou **`X-Idempotency-Key`**.
2. API v jedné transakci uloží platbu, outbox záznam a idempotenční klíč.
3. Worker periodicky načte nezpracované outbox záznamy a publikuje je do RabbitMQ.
4. Worker také každou hodinu maže expirované idempotenční klíče (TTL 24 h).

## Požadavky

- Docker a Docker Compose  
  nebo lokálně: Python 3.11+, běžící Postgres a RabbitMQ

## Spuštění (Docker)

```bash
docker compose up --build
```

Služby:

| Služba | URL / port |
|--------|------------|
| API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| RabbitMQ Management | http://localhost:15672 (guest / guest) |
| PostgreSQL | localhost:5432 |

## Lokální vývoj

1. Spusť infrastrukturu:

```bash
docker compose up db rabbitmq
```

2. Vytvoř `.env` v kořeni projektu:

```env
DATABASE_URL=postgresql+asyncpg://postgres:mysecretpassword@localhost:5432/zenpay
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
```

3. Virtuální prostředí a závislosti:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

4. API:

```bash
uvicorn app.main:app --reload
```

5. Worker (v druhém terminálu):

```bash
python -m app.worker
```

## API

### Health check

```http
GET /health
```

### Vytvoření platby

```http
POST /payments
X-Idempotency-Key: <unikátní-klíč>
Content-Type: application/json

{
  "user_id": 1,
  "amount": "1500.50",
  "currency": "CZK"
}
```

Odpověď `201`:

```json
{
  "id": 1,
  "status": "accepted"
}
```

Při opakování stejného `X-Idempotency-Key` API vrátí stejnou odpověď (idempotentní chování).

## Testy

```bash
pytest
```

## Stack

- **FastAPI** — HTTP API
- **SQLModel / SQLAlchemy** — ORM a modely
- **PostgreSQL** — perzistence
- **RabbitMQ** (aio-pika) — message broker
- **pytest** — testy
