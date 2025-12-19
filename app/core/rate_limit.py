import redis
from fastapi import HTTPException, Depends
from app.core.config import REDIS_URL, PLANS
from app.core.security import authenticate

redis_client = redis.from_url(REDIS_URL, decode_responses=True)
redis_client.ping()

def rate_limit(ctx=Depends(authenticate)):
    plan_cfg = PLANS[ctx["plan"]]
    key = f"rate:{ctx['consumer']}"

    current = redis_client.incr(key)
    if current == 1:
        redis_client.expire(key, 60)

    if current > plan_cfg["rpm"]:
        raise HTTPException(
            429,
            detail={
                "success": False,
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": "Too many requests"
                }
            }
        )
    return ctx
