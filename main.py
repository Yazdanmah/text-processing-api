from fastapi import FastAPI, Query, HTTPException, Header, Depends, Request
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict
from pydantic import BaseModel, Field
import re
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import redis

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
def get_valid_api_keys() -> List[str]:
    env_keys = os.getenv("API_KEYS", "")
    return [key.strip() for key in env_keys.split(",") if key.strip()]

def validate_api_key(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    x_rapidapi_key: Optional[str] = Header(None, alias="X-RapidAPI-Key"),
    x_rapidapi_proxy_secret: Optional[str] = Header(None, alias="X-RapidAPI-Proxy-Secret")
):
    if x_rapidapi_proxy_secret:
        if not x_rapidapi_key:
            raise HTTPException(
                status_code=403,
                detail={
                    "success": False,
                    "data": None,
                    "error": {
                        "code": "MISSING_RAPIDAPI_KEY",
                        "message": "X-RapidAPI-Key header is required"
                    }
                }
            )
        return x_rapidapi_key
    
    if not x_api_key:
        raise HTTPException(
            status_code=403,
            detail={
                "success": False,
                "data": None,
                "error": {
                    "code": "MISSING_API_KEY",
                    "message": "API key is required in X-API-Key header"
                }
            }
        )
    
    valid_keys = get_valid_api_keys()
    if x_api_key not in valid_keys:
        raise HTTPException(
            status_code=403,
            detail={
                "success": False,
                "data": None,
                "error": {
                    "code": "INVALID_API_KEY",
                    "message": "API key is not valid"
                }
            }
        )
    
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
                self.redis_client = redis.from_url(
                    os.getenv("REDIS_URL"),
                    decode_responses=True
                )
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
            self.memory_limits[key] = [
                req_time for req_time in self.memory_limits[key]
                if req_time > window_start
            ]
            if len(self.memory_limits[key]) >= limit:
                return False
            self.memory_limits[key].append(now)
            return True

rate_limiter_instance = RateLimiter()

def rate_limit(request: Request, api_key: str = Depends(validate_api_key)):
    if "rapidapi" in api_key.lower():
        limit = 100
    elif "pro" in api_key.lower():
        limit = 50
    else:
        limit = 10
    period_seconds = 60
    if not rate_limiter_instance.check_limit(api_key, limit, period_seconds):
        raise HTTPException(
            status_code=429,
            detail={
                "success": False,
                "data": None,
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": f"Rate limit exceeded. {limit} requests per minute allowed."
                }
            }
        )

# ----------------------
# Utilities
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

def get_text_stats(text: str) -> TextStats:
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
    return {
        "status": "healthy",
        "service": "Text Processing API",
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/health", include_in_schema=False)
def health_check():
    return {
        "status": "ok",
        "database": "connected" if rate_limiter_instance.use_redis else "memory",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/echo", response_model=APIResponse)
def echo(text: str = Query(..., min_length=1, max_length=1000)):
    return APIResponse(
        success=True,
        data={"echo": text, "length": len(text), "processed_at": datetime.utcnow().isoformat()},
        error=None
    )

@app.get("/text-utils", response_model=APIResponse)
def text_utils(
    text: str = Query(..., min_length=1, max_length=5000),
    action: str = Query(...),
    api_key: str = Depends(validate_api_key),
    _: str = Depends(rate_limit)
):
    action = action.lower().strip()
    if action == "clean":
        result = clean_text(text)
    elif action == "lower":
        result = text.lower()
    elif action == "upper":
        result = text.upper()
    elif action == "stats":
        result = get_text_stats(text).dict(exclude_none=True)
    elif action == "slug":
        result = slugify(text)
    else:
        raise HTTPException(status_code=400, detail={
            "success": False,
            "data": None,
            "error": {"code": "INVALID_ACTION", "message": f"Action '{action}' not supported"}
        })
    return APIResponse(success=True, data={"action": action, "original_length": len(text), "result": result, "processed_at": datetime.utcnow().isoformat()}, error=None)

class BatchTextRequest(BaseModel):
    texts: List[str] = Field(..., min_items=1, max_items=100)
    action: str = Field(...)

@app.post("/batch-process", response_model=APIResponse)
def batch_process(request: BatchTextRequest, api_key: str = Depends(validate_api_key), _: str = Depends(rate_limit)):
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
        else:
            raise HTTPException(status_code=400, detail={
                "success": False,
                "data": None,
                "error": {"code": "INVALID_ACTION", "message": f"Action '{request.action}' not supported"}
            })
        results.append({"original": text, "processed": result, "length_change": len(result)-len(text)})
    return APIResponse(success=True, data={"action": request.action, "total_texts": len(results), "results": results}, error=None)

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={
        "success": False,
        "data": None,
        "error": exc.detail if isinstance(exc.detail, dict) else {"code": "HTTP_ERROR", "message": str(exc.detail)}
    })
