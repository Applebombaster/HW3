import json
import nats
from app.ws.manager import ws_manager

NATS_URL = "nats://127.0.0.1:4222"
SUBJECT = "monitoring.events"

connection = None
is_connected = False

async def connect_nats():
    global connection, is_connected

    try:
        connection = await nats.connect(NATS_URL, connect_timeout=2)
        is_connected = True
        print("NATS подключен")

        async def handler(msg):
            try:
                data = json.loads(msg.data.decode())
                print(f"NATS получено: {data}")
                
                # Рассылаем всем WebSocket клиентам
                await ws_manager.broadcast_json({
                    "type": "nats.inbound",
                    "subject": msg.subject,
                    "payload": data
                })
                
            except Exception as e:
                print(f"Ошибка обработки NATS сообщения: {e}")
                await ws_manager.broadcast_json({
                    "type": "nats.error",
                    "error": str(e),
                    "raw_data": msg.data.decode(errors="ignore")
                })

        await connection.subscribe(SUBJECT, cb=handler)
        print(f"Подписан на тему: {SUBJECT}")
        return True
        
    except Exception as e:
        print(f"NATS: ошибка подключения ({e})")
        is_connected = False
        connection = None
        return False


async def close_nats():
    global connection, is_connected
    if connection is not None:
        try:
            await connection.drain()
            print("NATS соединение закрыто")
        except Exception as e:
            print(f"Ошибка при закрытии NATS: {e}")
    connection = None
    is_connected = False


async def publish_event(event: dict):
    # Публикация события в NATS
    if not is_connected or connection is None:
        return False
    try:
        await connection.publish(SUBJECT, json.dumps(event, default=str).encode())
        print(f"Опубликовано в NATS: {event['type']}")
        return True
    except Exception as e:
        print(f"Ошибка публикации в NATS: {e}")
        return False