import os
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL")
if not REDIS_URL:
    raise RuntimeError("REDIS_URL is required")

API_KEYS = os.getenv("API_KEYS", "")

PLANS = {
    "free": {
        "rpm": 10,
        "features": ["clean", "lower", "upper"],
        "batch_limit": 5,
    },
    "pro": {
        "rpm": 60,
        "features": ["clean", "lower", "upper", "slug"],
        "batch_limit": 20,
    },
    "ultra": {
        "rpm": 200,
        "features": ["clean", "lower", "upper", "slug", "stats", "batch"],
        "batch_limit": 100,
    },
    "rapidapi": {
        "rpm": 100,
        "features": ["clean", "lower", "upper", "slug", "stats", "batch"],
        "batch_limit": 50,
    }
}
