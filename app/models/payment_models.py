from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any
from sqlmodel import SQLModel, Field, Column, Numeric, JSON, DateTime

def get_utc_now():
    return datetime.now(timezone.utc)

class Payment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int
    amount: Decimal = Field(sa_column=Column(Numeric(precision=18, scale=2)))
    currency: str = Field(default="CZK") 
    status: str = Field(default="pending")
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True)),
        default_factory=get_utc_now
    )

class IdempotencyKey(SQLModel, table=True):
    key: str = Field(primary_key=True) # Změněno z id na key
    response_status: int
    response_body: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True)),
        default_factory=lambda: get_utc_now() + timedelta(hours=24)
    )

class Outbox(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    payment_id: int = Field(foreign_key="payment.id") 
    payload: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    processed_at: Optional[datetime] = Field(default=None)





