import asyncio
from typing import Optional
import time
import httpx
import socket
from sqlmodel import select
import ssl

from app.db.session import AsyncSessionLocal
from app.models.website import Website, ProtocolType
from app.models.check_result import CheckResult
from app.nats.client import publish_event
from app.ws.manager import ws_manager

_bg_task: Optional[asyncio.Task] = None


async def check_http(url: str) -> tuple[bool, Optional[int], float]:
    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, follow_redirects=True)
            latency = (time.perf_counter() - start) * 1000
            return resp.status_code < 500, resp.status_code, latency
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return False, None, latency


async def check_tcp(host: str, port: int = 80) -> tuple[bool, Optional[int], float]:
    start = time.perf_counter()
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=5
        )
        writer.close()
        await writer.wait_closed()
        latency = (time.perf_counter() - start) * 1000
        return True, None, latency
    except Exception:
        latency = (time.perf_counter() - start) * 1000
        return False, None, latency


async def run_check_cycle():
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Website).where(Website.is_active == True)
        )
        websites = result.scalars().all()
        
        for website in websites:
            try:
                is_up = False
                status_code = None
                response_time = 0.0
                error_msg = None
                
                if website.protocol in [ProtocolType.HTTP, ProtocolType.HTTPS]:
                    is_up, status_code, response_time = await check_http(website.url)
                elif website.protocol == ProtocolType.TCP:
                    # Извлекаем хост и порт из URL
                    host = website.url.replace("tcp://", "").split(":")[0]
                    port = int(website.url.split(":")[-1]) if ":" in website.url else 80
                    is_up, _, response_time = await check_tcp(host, port)
                
                check = CheckResult(
                    website_id=website.id,
                    is_up=is_up,
                    status_code=status_code,
                    response_time=response_time,
                    error_message=error_msg
                )
                session.add(check)
                
                # Отправляем в WebSocket
                await ws_manager.broadcast_json({
                    "type": "check.completed",
                    "payload": {
                        "website_id": website.id,
                        "website_name": website.name,
                        "is_up": is_up,
                        "response_time": response_time,
                        "checked_at": check.checked_at.isoformat()
                    }
                })
                
            except Exception as e:
                print(f"Error checking website {website.name}: {e}")
                continue
        
        await session.commit()
        
        event = {
            "type": "check.cycle.completed", 
            "payload": {"websites_checked": len(websites)}
        }
        await publish_event(event) or await ws_manager.broadcast_json(event)


async def checker_loop():
    while True:
        try:
            await run_check_cycle()
        except Exception as e:
            print(f"Checker error: {e}")
        await asyncio.sleep(60)  # Проверяем в написанный интервал времени


def start_background_checker() -> str:
    global _bg_task
    loop = asyncio.get_event_loop()
    if _bg_task and not _bg_task.done():
        return "Фоновая проверка уже запущена"
    _bg_task = loop.create_task(checker_loop())
    return "Фоновая проверка сайтов запущена"