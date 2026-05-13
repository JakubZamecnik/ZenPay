from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.db.session import engine
from sqlmodel import SQLModel
# Importy modelů jsou nutné, aby SQLModel věděl o existenci tabulek před create_all
from app.models.payment_models import Payment, IdempotencyKey, Outbox
from app.api.v1 import payments

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Kód zde se spustí PŘED startem aplikace (Startup)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield
    # Kód zde se spustí PO vypnutí aplikace (Shutdown) - nyní prázdné

app = FastAPI(title="ZenPay Fintech API", lifespan=lifespan)

# Připojení routeru pro platby
app.include_router(payments.router)

@app.get("/health")
async def health_check():
    return {"status": "running"}
