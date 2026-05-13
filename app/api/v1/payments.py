from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from app.db.session import get_session
from app.models.payment_models import Payment, IdempotencyKey, Outbox
from app.schemas.payment_schemas import PaymentCreate

router = APIRouter(prefix="/payments", tags=["payments"])

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_payment(
    payment_data: PaymentCreate,
    db: AsyncSession = Depends(get_session),
    x_idempotency_key: str = Header(...)
):
    # 1. Kontrola idempotence (Už jsme tuhle platbu viděli?)
    existing_key = await db.get(IdempotencyKey, x_idempotency_key)
    if existing_key:
        return existing_key.response_body

    try:
        # 2. Start transakce - buď se uloží všechno, nebo nic
        async with db.begin():
            # A. Vytvoření platby
            new_payment = Payment(
                user_id=payment_data.user_id,
                amount=payment_data.amount,
                currency=payment_data.currency,
                status="pending"
            )
            db.add(new_payment)
            await db.flush() # flush nám zjistí ID platby, ale ještě neposílá COMMIT

            # B. Záznam do Outboxu (aby Relay věděl, co poslat do RabbitMQ)
            outbox_entry = Outbox(
                payment_id=new_payment.id,
                payload={
                    "event": "payment_created",
                    "amount": str(new_payment.amount),
                    "user_id": new_payment.user_id
                }
            )
            db.add(outbox_entry)

            # C. Uložení idempotence klíče
            response_payload = {"id": new_payment.id, "status": "accepted"}
            idempotency = IdempotencyKey(
                key=x_idempotency_key,
                response_status=201,
                response_body=response_payload
            )
            db.add(idempotency)

            # Po skončení 'async with db.begin()' se provede automaticky COMMIT
            return response_payload

    except Exception as e:
        # Pokud se cokoli pokazí, SQLAlchemy udělá ROLLBACK automaticky
        print(f"Chyba při zpracování platby: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
