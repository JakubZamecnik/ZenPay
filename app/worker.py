import asyncio
import logging
from datetime import datetime, timezone
import aio_pika
from sqlmodel import select, delete
from app.config import settings
from app.db.session import async_session
from app.models.payment_models import Outbox, IdempotencyKey

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("outbox_worker")

async def clean_expired_idempotency_keys():
    """Úloha, která každou hodinu smaže expirované idempotenční klíče."""
    while True:
        try:
            async with async_session() as db:
                now = datetime.now(timezone.utc)
                # Smaž klíče, kde expires_at je menší než aktuální čas
                statement = delete(IdempotencyKey).where(IdempotencyKey.expires_at < now)
                result = await db.exec(statement)
                await db.commit()
                
                if result.rowcount > 0:
                    logger.info(f"Úklid: Smazáno {result.rowcount} expirovaných idempotenčních klíčů.")
        except Exception as e:
            logger.error(f"Chyba při čištění idempotenčních klíčů: {e}")
        
        # Počkej 1 hodinu (3600 sekund) před dalším úklidem
        await asyncio.sleep(3600)

async def process_outbox():
    connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
    
    async with connection:
        channel = await connection.channel()
        await channel.declare_queue("payment_events", durable=True)
        logger.info("Outbox Worker úspěšně nastartován a monitoruje databázi...")

        while True:
            async with async_session() as db:
                statement = select(Outbox).where(Outbox.processed_at == None).limit(10)
                results = await db.exec(statement)
                entries = results.all()

                for entry in entries:
                    try:
                        logger.info(f"Odesílám událost pro platbu ID {entry.payment_id}")
                        import json
                        message_body = json.dumps(entry.payload).encode()

                        await channel.default_exchange.publish(
                            aio_pika.Message(
                                body=message_body,
                                delivery_mode=aio_pika.DeliveryMode.PERSISTENT
                            ),
                            routing_key="payment_events",
                        )

                        entry.processed_at = datetime.now(timezone.utc)
                        db.add(entry)
                        await db.commit()
                        logger.info(f"Událost outboxu {entry.id} úspěšně zpracována.")

                    except Exception as e:
                        await db.rollback()
                        logger.error(f"Chyba při odesílání outbox záznamu {entry.id}: {e}")
            
            await asyncio.sleep(2)

async def main():
    # Spustíme obě asynchronní funkce paralelně vedle sebe
    await asyncio.gather(
        process_outbox(),
        clean_expired_idempotency_keys()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker ukončen uživatelem.")
