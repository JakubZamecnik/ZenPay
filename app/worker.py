import asyncio
import logging
import json
from datetime import datetime, timezone
import aio_pika
from sqlmodel import delete, text
from app.config import settings
from app.db.session import async_session
from app.models.payment_models import IdempotencyKey

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("outbox_worker")


async def clean_expired_idempotency_keys():
    """Úloha, která každou hodinu smaže expirované idempotenční klíče."""
    while True:
        try:
            async with async_session() as db:
                now = datetime.now(timezone.utc)
                statement = delete(IdempotencyKey).where(IdempotencyKey.expires_at < now)
                result = await db.exec(statement)
                await db.commit()

                if result.rowcount > 0:
                    logger.info(f"Úklid: Smazáno {result.rowcount} expirovaných idempotenčních klíčů.")
        except Exception as e:
            logger.error(f"Chyba při čištění idempotenčních klíčů: {e}")

        await asyncio.sleep(3600)


async def process_outbox():
    """Monitoruje databázi a asynchronně publikuje outbox záznamy do RabbitMQ."""
    while True:
        try:
            logger.info("Pokus o připojení k RabbitMQ...")
            connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)

            async with connection:
                channel = await connection.channel()
                await channel.declare_queue("payment_events", durable=True)
                logger.info("Outbox Worker úspěšně nastartován a monitoruje databázi...")

                while True:
                    async with async_session() as db:
                        # 1. Čtení čistých dat bez ORM mapování (zamezí greenlet chybě)
                        query = text(
                            "SELECT id, payment_id, payload FROM outbox WHERE processed_at IS NULL LIMIT 10"
                        )
                        result = await db.execute(query)
                        entries = result.fetchall()

                        for entry_id, payment_id, payload in entries:
                            try:
                                logger.info(f"Odesílám událost pro platbu ID {payment_id}")

                                if isinstance(payload, str):
                                    message_body = payload.encode()
                                else:
                                    message_body = json.dumps(payload).encode()

                                # 2. Publikace do RabbitMQ
                                await channel.default_exchange.publish(
                                    aio_pika.Message(
                                        body=message_body,
                                        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                                    ),
                                    routing_key="payment_events",
                                )

                                # 3. Čistý asynchronní update podle ID
                                update_stmt = text("UPDATE outbox SET processed_at = :now WHERE id = :id")
                                await db.execute(
                                    update_stmt,
                                    {
                                        "now": datetime.now(timezone.utc).replace(tzinfo=None),
                                        "id": entry_id,
                                    },
                                )
                                await db.commit()
                                logger.info(f"Událost outboxu {entry_id} úspěšně zpracována.")

                            except Exception as e:
                                await db.rollback()
                                logger.error(f"Chyba při odesílání outbox záznamu {entry_id}: {e}")

                    await asyncio.sleep(2)

        except (OSError, aio_pika.exceptions.AMQPConnectionError) as e:
            logger.warning(f"RabbitMQ server není dostupný ({e}). Nový pokus za 3 sekundy...")
            await asyncio.sleep(3)
        except Exception as e:
            logger.error(f"Neočekávaná chyba ve workeru: {e}. Restartuji smyčku za 5 sekund...")
            await asyncio.sleep(5)


async def main():
    await asyncio.gather(
        process_outbox(),
        clean_expired_idempotency_keys(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker ukončen uživatelem.")
