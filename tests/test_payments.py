import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_payment_idempotency():
    # Použijeme AsyncClient pro testování našeho FastAPI bez nutnosti spouštět uvicorn
    async with AsyncClient(app=app, base_url="http://test") as ac:
        
        headers = {"X-Idempotency-Key": "test-unique-key-12345"}
        payload = {
            "user_id": 999,
            "amount": "1500.50",
            "currency": "CZK"
        }

        # 1. První odeslání platby (Založení)
        response1 = await ac.post("/payments", json=payload, headers=headers)
        assert response1.status_code == 211 or response1.status_code == 201 # Přizpůsobí se podle stavu DB
        data1 = response1.json()
        assert "id" in data1
        assert data1["status"] == "accepted"

        # 2. Druhé odeslání se STEJNÝM klíčem (Idempotence)
        response2 = await ac.post("/payments", json=payload, headers=headers)
        data2 = response2.json()
        
        # Ověření, že druhý request dostal navlas stejnou odpověď (shodné ID platby)
        assert data1["id"] == data2["id"]
