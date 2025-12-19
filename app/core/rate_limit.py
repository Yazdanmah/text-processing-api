from datetime import datetime, timedelta
import redis
from fastapi import Depends, HTTPException, Request

from app.core.config import REDIS_URL, PLANS


class RateLimiter:
    def __init__(self):
        self.use_redis = False
        self.redis_client = None
        self.memory_limits = {}

        if REDIS_URL:
            try:
                self.redis_client = redis.from_url(
                    REDIS_URL, decode_responses=True
                )
                self.redis_client.ping()
                self.use_redis = True
            except Exception:
                self.use_redis = False
                self.redis_client = None

    def check_limit(self, key: str, limit: int, period_seconds: int) -> bool:
        if self.use_redis and self.redis_client:
            redis_key = f"ratelimit:{key}"
            current = self.redis_client.get(redis_key)

            if current and int(current) >= limit:
                return False

            pipe = self.redis_client.pipeline()
            pipe.incr(redis_key)
            pipe.expire(redis_key, period_seconds)
            pipe.execute()
            return True

        # -------- Memory fallback --------
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=period_seconds)

        if key not in self.memory_limits:
            self.memory_limits[key] = []

        self.memory_limits[key] = [
            t for t in self.memory_limits[key] if t > window_start
        ]

        if len(self.memory_limits[key]) >= limit:
            return False

        self.memory_limits[key].append(now)
        return True


# Singleton instance
rate_limiter = RateLimiter()


# --------------------------------------------------
# FastAPI dependency
# --------------------------------------------------
def rate_limit(request: Request):
    """
    Rate limit dependency for FastAPI routes
    """
    api_key = (
        request.headers.get("X-API-Key")
        or request.headers.get("X-RapidAPI-Key")
        or "anonymous"
    )

    plan = "free"
    for k, p in PLANS.items():
        if api_key.startswith(k):
            plan = k
            break

    rpm = PLANS.get(plan, {}).get("rpm", 10)

    if not rate_limiter.check_limit(api_key, rpm, 60):
        raise HTTPException(
            status_code=429,
            detail={
                "success": False,
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": "Too many requests"
                },
            },
        )

    return True
