import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables from configs/app.env
load_dotenv("configs/.env")

@dataclass
class Settings:
    app_name: str = os.getenv("APP_NAME", "RCA-RAG")
    app_env: str = os.getenv("APP_ENV", "development")
    app_host: str = os.getenv("APP_HOST", "0.0.0.0")
    app_port: int = os.getenv("APP_PORT", 8000)

    #gooogle chat
    google_chat_webhook_url: str = os.getenv("GOOGLE_CHAT_WEBHOOK_URL")
    google_chat_thread_key: str = os.getenv("GOOGLE_CHAT_THREAD_KEY")
    google_chat_notified_users: str = os.getenv("GOOGLE_CHAT_NOTIFIED_USERS", "")

settings = Settings()