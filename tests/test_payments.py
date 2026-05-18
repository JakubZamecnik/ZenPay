import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlmodel import SQLModel
# Změna zde: importujeme create_async_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from httpx import ASGITransport

from app.main import app
from app.db.session import get_session

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Změna zde: create_async_engine místo create_engine
engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

async_session_maker = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_database():
    """Před každým testem vytvoří čisté tabulky a po testu je smaže."""
    # Nyní již asynchronní kontextový manažer bude fungovat správně
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)

async def override_get_session() -> AsyncSession:
    """Nahradí produkční sešnu testovací sešnou."""
    async with async_session_maker() as session:
        yield session

# Promítneme override do naší FastAPI aplikace
app.dependency_overrides[get_session] = override_get_session


@pytest.mark.asyncio
async def test_payment_idempotency():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"X-Idempotency-Key": "test-unique-key-12345"}
        payload = {
            "user_id": 999,
            "amount": "1500.50",
            "currency": "CZK"
        }

        # 1. První odeslání platby (Založení)
        response1 = await ac.post("/payments", json=payload, headers=headers)
        assert response1.status_code == 201
        
        data1 = response1.json()
        assert "id" in data1
        assert data1["status"] == "accepted"

        # 2. Druhé odeslání se STEJNÝM klíčem (Idempotence)
        response2 = await ac.post("/payments", json=payload, headers=headers)
        assert response2.status_code == 201
        
        data2 = response2.json()
        
        # Ověření, že druhý request dostal navlas stejnou odpověď (shodné ID platby)
        assert data1["id"] == data2["id"]
        
    # Po skončení vyčistíme overrides, aby to neovlivnilo jiné testy
    app.dependency_overrides.clear()
