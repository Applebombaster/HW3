import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel, select
from datetime import datetime
import asyncio

from app.config import settings
from app.db.session import engine, AsyncSessionLocal

from app.api.routes.websites import router as websites_router
from app.api.routes.monitoring import router as monitoring_router
from app.ws.monitoring_ws import router as ws_monitoring_router
from app.nats.client import connect_nats, close_nats
from app.tasks.site_checker import start_background_checker
from app.models.website import Website, ProtocolType

app = FastAPI(
    title="Мониторинг Сайтов",
    version="Aльфа 0.1",
    docs_url="/docs",
    description="Система мониторинга доступности веб-сайтов",
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

async def seed_database():
    # Заполнение базы данных демо-сайтами при первом запуске
    async with AsyncSessionLocal() as session:
        # Проверяем, есть ли уже сайты в базе
        result = await session.execute(select(Website))
        existing_websites = result.scalars().all()
        
        if existing_websites:
            print(f"В базе уже есть {len(existing_websites)} сайтов")
            return False
        
        print("База данных пустая, загружаю демо-сайты...")
        
        # Список из 30 демо-сайтов для мониторинга
        demo_websites = [
            # Топ-10 глобальных сайтов
            {"name": "Google", "url": "https://google.com", "protocol": ProtocolType.HTTPS},
            {"name": "YouTube", "url": "https://youtube.com", "protocol": ProtocolType.HTTPS},
            {"name": "Facebook", "url": "https://facebook.com", "protocol": ProtocolType.HTTPS},
            {"name": "Wikipedia", "url": "https://wikipedia.org", "protocol": ProtocolType.HTTPS},
            {"name": "Twitter", "url": "https://twitter.com", "protocol": ProtocolType.HTTPS},
            {"name": "Instagram", "url": "https://instagram.com", "protocol": ProtocolType.HTTPS},
            {"name": "Reddit", "url": "https://reddit.com", "protocol": ProtocolType.HTTPS},
            {"name": "Amazon", "url": "https://amazon.com", "protocol": ProtocolType.HTTPS},
            {"name": "Netflix", "url": "https://netflix.com", "protocol": ProtocolType.HTTPS},
            {"name": "GitHub", "url": "https://github.com", "protocol": ProtocolType.HTTPS},
            
            # Российские сайты
            {"name": "Яндекс", "url": "https://ya.ru", "protocol": ProtocolType.HTTPS},
            {"name": "ВКонтакте", "url": "https://vk.com", "protocol": ProtocolType.HTTPS},
            {"name": "Mail.ru", "url": "https://mail.ru", "protocol": ProtocolType.HTTPS},
            {"name": "Одноклассники", "url": "https://ok.ru", "protocol": ProtocolType.HTTPS},
            {"name": "РБК", "url": "https://rbc.ru", "protocol": ProtocolType.HTTPS},
            {"name": "Tinkoff", "url": "https://tinkoff.ru", "protocol": ProtocolType.HTTPS},
            
            # Облачные сервисы и IT
            {"name": "AWS Status", "url": "https://status.aws.amazon.com", "protocol": ProtocolType.HTTPS},
            {"name": "Azure Status", "url": "https://status.azure.com", "protocol": ProtocolType.HTTPS},
            {"name": "Google Cloud", "url": "https://cloud.google.com", "protocol": ProtocolType.HTTPS},
            {"name": "Cloudflare", "url": "https://cloudflare.com", "protocol": ProtocolType.HTTPS},
            {"name": "DigitalOcean", "url": "https://digitalocean.com", "protocol": ProtocolType.HTTPS},
            
            # Новостные сайты
            {"name": "BBC News", "url": "https://bbc.com", "protocol": ProtocolType.HTTPS},
            {"name": "CNN", "url": "https://cnn.com", "protocol": ProtocolType.HTTPS},
            {"name": "Reuters", "url": "https://reuters.com", "protocol": ProtocolType.HTTPS},
            {"name": "The Guardian", "url": "https://theguardian.com", "protocol": ProtocolType.HTTPS},
            {"name": "Al Jazeera", "url": "https://aljazeera.com", "protocol": ProtocolType.HTTPS},
            
            # TCP сервисы (для демонстрации разных протоколов)
            {"name": "Google DNS", "url": "tcp://8.8.8.8:53", "protocol": ProtocolType.TCP},
            {"name": "Cloudflare DNS", "url": "tcp://1.1.1.1:53", "protocol": ProtocolType.TCP},
            {"name": "SSH GitHub", "url": "tcp://github.com:22", "protocol": ProtocolType.TCP},
            {"name": "SMTP Gmail", "url": "tcp://smtp.gmail.com:587", "protocol": ProtocolType.TCP},
            {"name": "HTTP Default", "url": "http://example.com", "protocol": ProtocolType.HTTP},
        ]
        
        # Создаем объекты сайтов
        websites_to_create = []
        for i, site_data in enumerate(demo_websites):
            # Делаем некоторые сайты неактивными для демонстрации
            is_active = not (i % 7 == 0)  # Каждый 7-й сайт неактивен
            
            website = Website(
                **site_data,
                is_active=is_active,
                check_interval=60,  # Проверка каждые 60 секунд
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            websites_to_create.append(website)
            
            if (i + 1) % 10 == 0:
                print(f"  Подготовлено {i + 1} сайтов...")
        
        # Добавляем все сайты в базу
        session.add_all(websites_to_create)
        await session.commit()
        
        # Получаем статистику
        result = await session.execute(select(Website))
        all_websites = result.scalars().all()
        
        # Считаем по протоколам
        https_count = sum(1 for w in all_websites if w.protocol in [ProtocolType.HTTPS, ProtocolType.HTTP])
        tcp_count = sum(1 for w in all_websites if w.protocol == ProtocolType.TCP)
        active_count = sum(1 for w in all_websites if w.is_active)
        
        print(f"Загружено {len(all_websites)} демо-сайтов")
        print(f"Статистика:")
        print(f"   - {https_count} HTTP/HTTPS сайтов")
        print(f"   - {tcp_count} TCP сервисов")
        print(f"   - {active_count} активных, {len(all_websites) - active_count} неактивных")
        print(f"   - Интервал проверки: 60 секунд")
        
        return True

async def generate_initial_check_results():
    # Генерация начальных результатов проверок для демонстрации
    import random
    from datetime import datetime, timedelta
    from app.models.check_result import CheckResult
    
    async with AsyncSessionLocal() as session:
        # Проверяем, есть ли уже результаты проверок
        result = await session.execute(select(CheckResult))
        existing_checks = result.scalars().all()
        
        if existing_checks:
            print(f"В базе уже есть {len(existing_checks)} результатов проверок")
            return
        
        print("Генерация начальной истории проверок...")
        
        # Получаем все сайты
        result = await session.execute(select(Website))
        websites = result.scalars().all()
        
        if not websites:
            print("Нет сайтов для генерации проверок")
            return
        
        check_results = []
        
        # Для каждого сайта создаем 3-5 исторических проверок
        for website in websites:
            num_checks = random.randint(3, 5)
            
            for i in range(num_checks):
                # Случайно определяем успешность проверки (90% успешных)
                is_up = random.random() < 0.9
                
                # Для HTTP/HTTPS сайтов генерируем статус код
                status_code = None
                if website.protocol in [ProtocolType.HTTP, ProtocolType.HTTPS]:
                    if is_up:
                        status_code = random.choice([200, 201, 204])
                    else:
                        status_code = random.choice([404, 500, 502, 503])
                
                # Генерируем время ответа
                response_time = random.uniform(50, 300) if is_up else random.uniform(1000, 5000)
                
                # Генерируем время проверки (от 1 до 24 часов назад)
                hours_ago = random.randint(1, 24)
                checked_at = datetime.utcnow() - timedelta(hours=hours_ago)
                
                check_result = CheckResult(
                    website_id=website.id,
                    is_up=is_up,
                    status_code=status_code,
                    response_time=response_time,
                    error_message=None if is_up else "Connection timeout",
                    checked_at=checked_at
                )
                check_results.append(check_result)
        
        session.add_all(check_results)
        await session.commit()
        
        print(f"Сгенерировано {len(check_results)} исторических проверок")
        print(f"Период: последние 24 часа")

@app.on_event("startup")
async def on_startup():
    # Действия при запуске приложения
    print("Запуск системы мониторинга сайтов...")
    
    # Создаем таблицы в базе данных
    try:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
        print("Таблицы базы данных созданы")
    except Exception as e:
        print(f"Ошибка при создании таблиц БД: {e}")
        return
    
    # Заполняем базу демо-данными
    try:
        db_seeded = await seed_database()
        
        # Если база была заполнена, генерируем историю проверок
        if db_seeded:
            await generate_initial_check_results()
    except Exception as e:
        print(f"Ошибка при заполнении базы данных: {e}")
        print("Приложение продолжит работу с пустой базой")
    
    # Подключаемся к NATS
    try:
        nats_connected = await connect_nats()
        if nats_connected:
            print("NATS подключен")
        else:
            print("NATS не подключен, работаем без него")
    except Exception as e:
        print(f"Ошибка подключения к NATS: {e}")
    
    # Запускаем фоновую проверку сайтов
    try:
        start_background_checker()
        print("Фоновая проверка сайтов запущена")
        print("Интервал проверки: 60 секунд")
    except Exception as e:
        print(f"Ошибка запуска фоновой проверки: {e}")
    
    # Итоговая информация
    print("\n" + "="*50)
    print("Система мониторинга успешно запущена!")
    print("="*50)
    print("Доступные интерфейсы:")
    print("   - REST API: http://localhost:8000/docs")
    print("   - WebSocket: ws://localhost:8000/ws/monitoring")
    print("   - База данных: monitoring.db (SQLite)")
    print("\nДемо-данные:")
    print("   - 30 сайтов для мониторинга")
    print("   - Разные протоколы: HTTPS, HTTP, TCP")
    print("   - История проверок за последние 24 часа")
    print("="*50)


@app.on_event("shutdown")
async def on_shutdown():
    # Действия при остановке приложения
    print("\nОстановка системы мониторинга...")
    
    try:
        await close_nats()
        print("NATS соединение закрыто")
    except Exception as e:
        print(f"Ошибка при закрытии NATS: {e}")
    
    print("Система мониторинга остановлена")


# Подключаем роутеры
app.include_router(websites_router)
app.include_router(monitoring_router)
app.include_router(ws_monitoring_router)


# Эндпоинт для проверки здоровья системы
@app.get("/health")
async def health_check():
    # Проверка здоровья системы
    return {
        "status": "healthy",
        "service": "Мониторинг Сайтов",
        "version": "Aльфа 0.1",
        "timestamp": datetime.utcnow().isoformat(),
        "endpoints": {
            "docs": "/docs",
            "websocket": "/ws/monitoring",
            "websites": "/websites",
            "monitoring": "/monitoring"
        }
    }


# Эндпоинт для получения информации о системе
@app.get("/")
async def root():
    # Корневой эндпоинт с информацией о системе
    return {
        "message": "Добро пожаловать в систему мониторинга веб-сайтов!",
        "documentation": "Документация доступна по адресу /docs",
        "version": "Aльфа 0.1",
        "features": [
            "Мониторинг 30+ популярных сайтов",
            "Поддержка HTTP, HTTPS и TCP протоколов",
            "Real-time уведомления через WebSocket",
            "REST API для управления",
            "Фоновая проверка каждые 60 секунд",
            "История проверок с метриками"
        ],
        "quick_start": [
            "1. Откройте /docs для работы с API",
            "2. Подключитесь к /ws/monitoring для real-time событий",
            "3. Используйте /websites для управления сайтами",
            "4. Используйте /monitoring для управления проверками"
        ]
    }


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )