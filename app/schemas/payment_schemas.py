from pydantic import BaseModel
from decimal import Decimal

class PaymentCreate(BaseModel):
    user_id: int
    amount: Decimal
    currency: str = "CZK"

    class Config:
        # Tohle umožní Pydanticu pracovat s Decimalem správně
        json_encoders = {
            Decimal: lambda v: str(v)
        }
