from fastapi import FastAPI, Query, HTTPException, Header, Depends, Request
from typing import Optional, List, Dict
from pydantic import BaseModel, Field
import re
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import redis
import json

# ----------------------
# Configuration
# ----------------------
load_dotenv()

app = FastAPI(
    title="Text Processing API Pro",
    description="Professional text processing utilities for developers",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    contact={
        "name": "API Support",
        "email": "support@example.com",
    },
    license_info={
        "name": "Commercial",
        "url": "https://example.com/license",
    }
)

# ----------------------
# Models
# ----------------------
class ErrorDetail(BaseModel):
    code: str = Field(..., example="INVALID_API_KEY")
    message: str = Field(..., example="API key is not valid")

class APIResponse(BaseModel):
    success: bool = Field(..., example=True)
    data: Optional[Dict] = None
    error: Optional[ErrorDetail] = None

class TextStats(BaseModel):
    length: int = Field(..., example=42)
    words: int = Field(..., example=7)
    characters_without_spaces: int = Field(..., example=35)
    sentences: Optional[int] = Field(None, example=2)
    reading_time_minutes: Optional[float] = Field(None, example=0.1)

# ----------------------
# Authentication
# ----------------------
def get_valid_api_keys() -> Dict[str, str]:
    """Return a dictionary of api_key -> plan"""
    env_keys = os.getenv("API_KEYS", "")
    # Example format: key1:free,key2:pro,key3:ultra
    keys = {}
    for pair in env_keys.split(","):
        if ":" in pair:
            k, p = pair.split(":")
            keys[k.strip()] = p.strip().lower()
    return keys

def validate_api_key(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    x_rapidapi_key: Optional[str] = Header(None, alias="X-RapidAPI-Key"),
    x_rapidapi_proxy_secret: Optional[str] = Header(None, alias="X-RapidAPI-Proxy-Secret")
):
    keys = get_valid_api_keys()
    
    # RapidAPI flow
    if x_rapidapi_proxy_secret:
        if not x_rapidapi_key:
            raise HTTPException(status_code=403, detail={
                "success": False,
                "data": None,
                "error": {"code": "MISSING_RAPIDAPI_KEY", "message": "X-RapidAPI-Key required"}
            })
        # Treat all RapidAPI keys as pro for example
        return "rapidapi_pro"
    
    if not x_api_key or x_api_key not in keys:
        raise HTTPException(status_code=403, detail={
            "success": False,
            "data": None,
            "error": {"code": "INVALID_API_KEY", "message": "API key not valid"}
        })
    return x_api_key

# ----------------------
# Rate Limiting
# ----------------------
class RateLimiter:
    def __init__(self):
        self.redis_client = None
        self.use_redis = os.getenv("REDIS_URL") is not None
        if self.use_redis:
            try:
                self.redis_client = redis.from_url(os.getenv("REDIS_URL"), decode_responses=True)
                self.redis_client.ping()
            except redis.ConnectionError:
                self.use_redis = False
        self.memory_limits = {}

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
        else:
            now = datetime.utcnow()
            window_start = now - timedelta(seconds=period_seconds)
            if key not in self.memory_limits:
                self.memory_limits[key] = []
            self.memory_limits[key] = [t for t in self.memory_limits[key] if t > window_start]
            if len(self.memory_limits[key]) >= limit:
                return False
            self.memory_limits[key].append(now)
            return True

rate_limiter_instance = RateLimiter()

def rate_limit(request: Request, api_key: str = Depends(validate_api_key)):
    # Assign rate limits by plan
    plan_map = get_valid_api_keys()
    plan = plan_map.get(api_key, "free")
    
    limits = {
        "free": 10,
        "pro": 50,
        "ultra": 100,
        "mega": 200,
        "rapidapi_pro": 100
    }
    period = 60
    if not rate_limiter_instance.check_limit(api_key, limits.get(plan, 10), period):
        raise HTTPException(status_code=429, detail={
            "success": False,
            "data": None,
            "error": {"code": "RATE_LIMIT_EXCEEDED", "message": f"Rate limit exceeded for {plan} plan"}
        })
    return True

# ----------------------
# Feature and Plan Restrictions
# ----------------------
feature_map = {
    "free": ["clean", "lower", "upper"],
    "pro": ["clean", "lower", "upper", "slug"],
    "ultra": ["clean", "lower", "upper", "slug", "stats", "batch"],
    "mega": ["clean", "lower", "upper", "slug", "stats", "batch"],
    "rapidapi_pro": ["clean", "lower", "upper", "slug", "stats", "batch"]
}

batch_limits = {
    "free": 5,
    "pro": 10,
    "ultra": 50,
    "mega": 100,
    "rapidapi_pro": 50
}

def check_feature(api_key: str, action: str):
    plan = get_valid_api_keys().get(api_key, "free")
    allowed = feature_map.get(plan, [])
    if action not in allowed:
        raise HTTPException(status_code=403, detail={
            "success": False,
            "data": None,
            "error": {"code": "FEATURE_NOT_AVAILABLE", "message": f"Action '{action}' not available for {plan} plan"}
        })
    return plan

# ----------------------
# Utility Functions
# ----------------------
def clean_text(text: str) -> str:
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text

def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text

def get_text_stats(text: str):
    words = text.split()
    sentences = len(re.split(r'[.!?]+', text))
    reading_time = len(words) / 200
    return TextStats(
        length=len(text),
        words=len(words),
        characters_without_spaces=len(text.replace(" ", "")),
        sentences=sentences if sentences > 0 else None,
        reading_time_minutes=round(reading_time, 2)
    )

# ----------------------
# Endpoints
# ----------------------
@app.get("/", response_model=Dict)
def root():
    return {"status": "healthy", "service": "Text Processing API", "version": "2.0.0", "timestamp": datetime.utcnow().isoformat()}

@app.get("/health", include_in_schema=False)
def health_check():
    return {"status": "ok", "database": "connected" if rate_limiter_instance.use_redis else "memory", "timestamp": datetime.utcnow().isoformat()}

@app.get("/text-utils", response_model=APIResponse)
def text_utils(
    text: str = Query(..., min_length=1, max_length=5000),
    action: str = Query(...),
    api_key: str = Depends(validate_api_key),
    _: str = Depends(rate_limit)
):
    action = action.lower().strip()
    plan = check_feature(api_key, action)
    
    if action == "clean":
        result = clean_text(text)
    elif action == "lower":
        result = text.lower()
    elif action == "upper":
        result = text.upper()
    elif action == "slug":
        result = slugify(text)
    elif action == "stats":
        result = get_text_stats(text).dict(exclude_none=True)
    else:
        raise HTTPException(status_code=400, detail={
            "success": False,
            "data": None,
            "error": {"code": "INVALID_ACTION", "message": f"Action '{action}' not supported"}
        })
    return APIResponse(success=True, data={"action": action, "original_length": len(text), "result": result, "processed_at": datetime.utcnow().isoformat()}, error=None)

class BatchTextRequest(BaseModel):
    texts: List[str] = Field(..., min_items=1)
    action: str = Field(...)

@app.post("/batch-process", response_model=APIResponse)
def batch_process(
    request: BatchTextRequest,
    api_key: str = Depends(validate_api_key),
    _: str = Depends(rate_limit)
):
    plan = check_feature(api_key, "batch")
    max_batch = batch_limits.get(plan, 5)
    if len(request.texts) > max_batch:
        raise HTTPException(status_code=403, detail={
            "success": False,
            "data": None,
            "error": {"code": "BATCH_LIMIT_EXCEEDED", "message": f"Batch limit {max_batch} exceeded for {plan} plan"}
        })
    
    results = []
    for text in request.texts:
        if request.action == "clean":
            result = clean_text(text)
        elif request.action == "lower":
            result = text.lower()
        elif request.action == "upper":
            result = text.upper()
        elif request.action == "slug":
            result = slugify(text)
        elif request.action == "stats":
            result = get_text_stats(text).dict(exclude_none=True)
        else:
            raise HTTPException(status_code=400, detail={
                "success": False,
                "data": None,
                "error": {"code": "INVALID_ACTION", "message": f"Action '{request.action}' not supported"}
            })
        results.append({"original": text, "processed": result, "length_change": len(result)-len(text)})
    
    return APIResponse(success=True, data={
        "action": request.action,
        "total_texts": len(results),
        "results": results,
        "summary": {"total_characters_processed": sum(len(r["original"]) for r in results), "average_length": sum(len(r["original"]) for r in results)/len(results)}
    }, error=None)
