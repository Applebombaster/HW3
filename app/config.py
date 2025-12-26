import os

class Settings:
    app_name: str = "Мониторинг Сайтов"
    version: str = "Aльфа 0.1"
    debug: bool = True
    database_url: str = "sqlite+aiosqlite:///./monitoring.db"

settings = Settings()