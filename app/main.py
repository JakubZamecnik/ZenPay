from fastapi import FastAPI
from app.db.session import engine
from sqlmodel import SQLModel
# Tyto importy teď budou fungovat, protože soubory existují
from app.models.payment_models import Payment, IdempotencyKey, Outbox
from app.api.v1 import payments

app = FastAPI(title="ZenPay Fintech API")
app.include_router(payments.router)

@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        # Vytvoří tabulky v Postgresu
        await conn.run_sync(SQLModel.metadata.create_all)

@app.get("/health")
async def health_check():
    return {"status": "running"}

