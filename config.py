import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-in-production")
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "spp_fenrir")
    XENDIT_API_KEY = os.getenv("XENDIT_API_KEY", "")
    APP_TITLE = os.getenv("APP_TITLE", "Aplikasi SPP Sekolah")
    APP_NAME = os.getenv("APP_NAME", "Aplikasi SPP Sekolah")
    APP_ADDRESS = os.getenv("APP_ADDRESS", "Jl. Raya Tangerang No. 1")
    APP_PHONE = os.getenv("APP_PHONE", "(021) 1234567")
    DEV_MODE = os.getenv("FENRIR_DEV_MODE", "1") == "1"

    XENDIT_API_URL = "https://api.xendit.co"
    XENDIT_CALLBACK_TOKEN = os.getenv("XENDIT_CALLBACK_TOKEN", "")

    HAS_XENDIT = bool(XENDIT_API_KEY)
