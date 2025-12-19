import os
from dotenv import load_dotenv

load_dotenv()

# --------------------------------------------------
# Optional Redis configuration
# --------------------------------------------------
# If REDIS_URL is not set, the app will use
# in-memory rate limiting as a fallback.
REDIS_URL = os.getenv("REDIS_URL")  # Optional, DO NOT enforce

# --------------------------------------------------
# API Keys configuration
# Format: key1:free,key2:pro,key3:ultra
# --------------------------------------------------
API_KEYS = os.getenv("API_KEYS", "")

# --------------------------------------------------
# Plans configuration (commercial-ready)
# --------------------------------------------------
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
    "mega": {
        "rpm": 400,
        "features": ["clean", "lower", "upper", "slug", "stats", "batch"],
        "batch_limit": 200,
    },
    "rapidapi_pro": {
        "rpm": 100,
        "features": ["clean", "lower", "upper", "slug", "stats", "batch"],
        "batch_limit": 50,
    },
}
