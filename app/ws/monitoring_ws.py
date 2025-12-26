import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.ws.manager import ws_manager

router = APIRouter()


@router.websocket("/ws/monitoring")
async def ws_monitoring(ws: WebSocket):
    await ws_manager.connect(ws)
    
    # Отправляем приветственное сообщение
    await ws.send_json({
        "type": "welcome",
        "message": "Подключено к системе мониторинга сайтов",
        "supported_events": [
            "website.created",
            "website.updated", 
            "website.deleted",
            "check.completed",
            "check.cycle.completed",
            "nats.inbound"
        ]
    })
    
    async def send_heartbeat():
        while True:
            await asyncio.sleep(30)
            try:
                await ws.send_json({
                    "type": "heartbeat",
                    "timestamp": asyncio.get_event_loop().time()
                })
            except:
                break
    
    heartbeat_task = asyncio.create_task(send_heartbeat())
    
    try:
        while True:
            try:
                data = await ws.receive_text()
                
                if data == "Кто ты воин?":
                    await ws.send_json({"type": "Я Ахилес, сын Пелея", "timestamp": asyncio.get_event_loop().time()})
                elif data.startswith("subscribe:"):
                    # Простая система подписки на события
                    event_type = data.split(":")[1]
                    await ws.send_json({
                        "type": "subscription",
                        "event": event_type,
                        "status": "subscribed"
                    })
                else:
                    await ws.send_json({
                        "type": "echo",
                        "received": data,
                        "timestamp": asyncio.get_event_loop().time()
                    })
                    
            except WebSocketDisconnect:
                break
    finally:
        heartbeat_task.cancel()
        await ws_manager.disconnect(ws)