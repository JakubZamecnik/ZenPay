from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

# TADY POZOR: Heslo musí být 'mysecretpassword' jako v Dockeru
DATABASE_URL = "postgresql+asyncpg://postgres:mysecretpassword@localhost:5432/zenpay"

engine = create_async_engine(DATABASE_URL, echo=True)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session

