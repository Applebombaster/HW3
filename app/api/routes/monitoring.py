from fastapi import APIRouter
from app.tasks.site_checker import start_background_checker, run_check_cycle

router = APIRouter(prefix="/monitoring", tags=["Monitoring"])


@router.post("/run-check")
async def run_single_check():
    await run_check_cycle()
    return {"message": "Одиночная проверка выполнена"}


@router.post("/start-background")
async def start_background_monitoring():
    msg = start_background_checker()
    return {"message": msg}


@router.get("/status")
async def get_monitoring_status():
    return {
        "status": "active",
        "description": "Система мониторинга веб-сайтов",
        "check_interval": "60 секунд"
    }