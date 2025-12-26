from typing import List
from fastapi import WebSocket
from fastapi.encoders import jsonable_encoder


class WSManager:
    def __init__(self) -> None:
        self.active: List[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.append(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        try:
            await ws.close()
        except Exception:
            pass
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast_json(self, data) -> None:
        to_remove = []
        for ws in list(self.active):
            try:
                await ws.send_json(jsonable_encoder(data))
            except Exception:
                to_remove.append(ws)
        for ws in to_remove:
            await self.disconnect(ws)


ws_manager = WSManager()