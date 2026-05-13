from fastapi import APIRouter, Depends, Header, HTTPException, status, Response
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.exc import IntegrityError
from app.db.session import get_session
from app.models.payment_models import Payment, IdempotencyKey, Outbox
from app.schemas.payment_schemas import PaymentCreate

router = APIRouter(prefix="/payments", tags=["payments"])

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_payment(
    payment_data: PaymentCreate,
    response: Response,
    db: AsyncSession = Depends(get_session),
    x_idempotency_key: str = Header(...)
):
    # 1. Rychlá kontrola existujícího klíče před spuštěním zápisu
    existing_key = await db.get(IdempotencyKey, x_idempotency_key)
    if existing_key:
        response.status_code = existing_key.response_status
        return existing_key.response_body

    # 2. Zápis do databáze
    try:
        # A. Vytvoření platby
        new_payment = Payment(
            user_id=payment_data.user_id,
            amount=payment_data.amount,
            currency=payment_data.currency,
            status="pending"
        )
        db.add(new_payment)
        await db.flush()  # Získáme ID platby pro outbox

        # B. Záznam do Outboxu
        outbox_entry = Outbox(
            payment_id=new_payment.id,
            payload={
                "event": "payment_created",
                "payment_id": new_payment.id,
                "amount": str(new_payment.amount),
                "user_id": new_payment.user_id
            }
        )
        db.add(outbox_entry)

        # C. Uložení idempotence klíče
        response_payload = {"id": new_payment.id, "status": "accepted"}
        idempotency = IdempotencyKey(
            key=x_idempotency_key,
            response_status=status.HTTP_201_CREATED,
            response_body=response_payload
        )
        db.add(idempotency)

        # Potvrzení celé transakce najednou
        await db.commit()
        return response_payload

    except IntegrityError:
        # Zachycení Race Condition: Jiný vlákno zapsalo stejný klíč těsně před námi
        await db.rollback()
        
        # Načteme data, která tam stihl zapsat první úspěšný požadavek
        existing_key = await db.get(IdempotencyKey, x_idempotency_key)
        if existing_key:
            response.status_code = existing_key.response_status
            return existing_key.response_body
        
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database conflict")
        
    except Exception as e:
        await db.rollback()
        print(f"Chyba při zpracování platby: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal Server Error")
