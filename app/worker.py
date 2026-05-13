import asyncio
import logging
from datetime import datetime, timezone
import aio_pika
from sqlmodel import select
from app.config import settings
from app.db.session import async_session
from app.models.payment_models import Outbox

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("outbox_worker")

async def process_outbox():
    # 1. Připojení k RabbitMQ
    connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
    
    async with connection:
        channel = await connection.channel()
        # Vytvoření fronty (pokud neexistuje)
        queue = await channel.declare_queue("payment_events", durable=True)
        
        logger.info("Outbox Worker úspěšně nastartován a monitoruje databázi...")

        while True:
            # Otevřeme novou DB session pro každou kontrolu
            async with async_session() as db:
                # Vyhledání nezpracovaných zpráv (processed_at je None)
                statement = select(Outbox).where(Outbox.processed_at == None).limit(10)
                results = await db.exec(statement)
                entries = results.all()

                for entry in entries:
                    try:
                        logger.info(f"Odesílám událost pro platbu ID {entry.payment_id}")
                        
                        # Serializace payloadu z JSON do stringu/bytes
                        import json
                        message_body = json.dumps(entry.payload).encode()

                        # Odeslání do RabbitMQ fronty
                        await channel.default_exchange.publish(
                            aio_pika.Message(
                                body=message_body,
                                delivery_mode=aio_pika.DeliveryMode.PERSISTENT
                            ),
                            routing_key="payment_events",
                        )

                        # Označení v DB jako zpracované
                        entry.processed_at = datetime.now(timezone.utc)
                        db.add(entry)
                        await db.commit()
                        logger.info(f"Událost outboxu {entry.id} úspěšně zpracována.")

                    except Exception as e:
                        await db.rollback()
                        logger.error(f"Chyba při odesílání outbox záznamu {entry.id}: {e}")
            
            # Počkej 2 sekundy před další kontrolou databáze
            await asyncio.sleep(2)

if __name__ == "__main__":
    try:
        asyncio.run(process_outbox())
    except KeyboardInterrupt:
        logger.info("Worker ukončen uživatelem.")
