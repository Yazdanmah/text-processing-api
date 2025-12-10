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
def get_valid_api_keys() -> List[str]:
    """Get API keys from environment or database"""
    env_keys = os.getenv("API_KEYS", "")
    return [key.strip() for key in env_keys.split(",") if key.strip()]

def validate_api_key(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    x_rapidapi_key: Optional[str] = Header(None, alias="X-RapidAPI-Key"),
    x_rapidapi_proxy_secret: Optional[str] = Header(None, alias="X-RapidAPI-Proxy-Secret")
):
    """
    Validate API key from multiple sources:
    1. Direct API users (X-API-Key)
    2. RapidAPI users (X-RapidAPI-Key)
    """
    
    # Case 1: RapidAPI request
    if x_rapidapi_proxy_secret:
        # This is a request coming through RapidAPI
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
        # Here you can validate RapidAPI specific logic
        # For now, we'll accept any RapidAPI key
        return x_rapidapi_key
    
    # Case 2: Direct API request
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
    
    # Validate direct API key
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
# Rate Limiting with Redis
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
        
        # In-memory fallback
        self.memory_limits = {}
    
    def check_limit(self, key: str, limit: int, period_seconds: int) -> bool:
        """Check if request is within rate limit"""
        
        if self.use_redis and self.redis_client:
            # Redis implementation
            redis_key = f"ratelimit:{key}"
            current = self.redis_client.get(redis_key)
            
            if current and int(current) >= limit:
                return False
            
            # Increment with pipeline
            pipe = self.redis_client.pipeline()
            pipe.incr(redis_key)
            pipe.expire(redis_key, period_seconds)
            pipe.execute()
            return True
        else:
            # In-memory implementation
            now = datetime.utcnow()
            window_start = now - timedelta(seconds=period_seconds)
            
            if key not in self.memory_limits:
                self.memory_limits[key] = []
            
            # Clean old requests
            self.memory_limits[key] = [
                req_time for req_time in self.memory_limits[key]
                if req_time > window_start
            ]
            
            if len(self.memory_limits[key]) >= limit:
                return False
            
            self.memory_limits[key].append(now)
            return True

rate_limiter_instance = RateLimiter()

def rate_limit(
    request: Request,
    api_key: str = Depends(validate_api_key)
):
    """Apply rate limiting based on API key"""
    
    # Different limits for different keys
    if "rapidapi" in api_key.lower():
        # RapidAPI users have higher limits
        limit = 100
    elif "pro" in api_key.lower():
        # Pro users
        limit = 50
    else:
        # Free users
        limit = 10
    
    period_seconds = 60  # 1 minute
    
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
# Utility Functions
# ----------------------
def clean_text(text: str) -> str:
    """Remove extra whitespace"""
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text

def slugify(text: str) -> str:
    """Convert text to URL-friendly slug"""
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text

def get_text_stats(text: str) -> TextStats:
    """Get comprehensive text statistics"""
    words = text.split()
    sentences = len(re.split(r'[.!?]+', text))
    
    # Calculate reading time (average 200 words per minute)
    reading_time = len(words) / 200
    
    return TextStats(
        length=len(text),
        words=len(words),
        characters_without_spaces=len(text.replace(" ", "")),
        sentences=sentences if sentences > 0 else None,
        reading_time_minutes=round(reading_time, 2)
    )

# ----------------------
# Health Check Endpoint
# ----------------------
@app.get("/", response_model=Dict)
def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Text Processing API",
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/health", include_in_schema=False)
def health_check():
    """Detailed health check"""
    return {
        "status": "ok",
        "database": "connected" if rate_limiter_instance.use_redis else "memory",
        "timestamp": datetime.utcnow().isoformat()
    }

# ----------------------
# Echo Endpoint
# ----------------------
@app.get("/echo", response_model=APIResponse)
def echo(
    text: str = Query(
        ...,
        min_length=1,
        max_length=1000,
        description="Text to echo back",
        example="Hello, World!"
    )
):
    """
    Echo endpoint that returns the input text and its length.
    
    Useful for testing API connectivity and response format.
    """
    if text.lower() == "test":
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "data": None,
                "error": {
                    "code": "INVALID_TEXT",
                    "message": "The word 'test' is not allowed in this context"
                }
            }
        )
    
    return APIResponse(
        success=True,
        data={
            "echo": text,
            "length": len(text),
            "processed_at": datetime.utcnow().isoformat()
        },
        error=None
    )

# ----------------------
# Text Utilities Endpoint
# ----------------------
@app.get(
    "/text-utils",
    response_model=APIResponse,
    summary="Text Processing Utilities",
    description="""
    Perform various text processing operations.
    
    Available actions:
    - **clean**: Remove extra whitespace
    - **lower**: Convert to lowercase
    - **upper**: Convert to uppercase
    - **stats**: Get text statistics (length, words, etc.)
    - **slug**: Convert to URL-friendly slug
    """
)
def text_utils(
    text: str = Query(
        ...,
        min_length=1,
        max_length=5000,
        description="Input text to process",
        example="Hello  World! This is a  test."
    ),
    action: str = Query(
        ...,
        description="Processing action to apply",
        example="clean"
    ),
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
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "data": None,
                "error": {
                    "code": "INVALID_ACTION",
                    "message": f"Action '{action}' is not supported. "
                              "Available actions: clean, lower, upper, stats, slug"
                }
            }
        )
    
    return APIResponse(
        success=True,
        data={
            "action": action,
            "original_length": len(text),
            "result": result,
            "processed_at": datetime.utcnow().isoformat()
        },
        error=None
    )

# ----------------------
# Batch Processing Endpoint
# ----------------------
class BatchTextRequest(BaseModel):
    texts: List[str] = Field(..., min_items=1, max_items=100)
    action: str = Field(..., example="clean")

@app.post(
    "/batch-process",
    response_model=APIResponse,
    summary="Batch Text Processing",
    description="Process multiple texts in a single request"
)
def batch_process(
    request: BatchTextRequest,
    api_key: str = Depends(validate_api_key),
    _: str = Depends(rate_limit)
):
    """Process multiple texts with the same action"""
    
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
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "data": None,
                    "error": {
                        "code": "INVALID_ACTION",
                        "message": f"Action '{request.action}' is not supported"
                    }
                }
            )
        
        results.append({
            "original": text,
            "processed": result,
            "length_change": len(result) - len(text)
        })
    
    return APIResponse(
        success=True,
        data={
            "action": request.action,
            "total_texts": len(results),
            "results": results,
            "summary": {
                "total_characters_processed": sum(len(r["original"]) for r in results),
                "average_length": sum(len(r["original"]) for r in results) / len(results)
            }
        },
        error=None
    )

# ----------------------
# Error Handlers
# ----------------------
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom HTTP exception handler"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "data": None,
            "error": {
                "code": exc.detail.get("code", "HTTP_ERROR"),
                "message": exc.detail.get("message", str(exc.detail))
            }
        }
    )

# ----------------------
# Middleware for Logging
# ----------------------
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all API requests"""
    start_time = datetime.utcnow()
    
    response = await call_next(request)
    
    process_time = (datetime.utcnow() - start_time).total_seconds() * 1000
    
    # Log request details (you can save to database here)
    log_data = {
        "timestamp": start_time.isoformat(),
        "method": request.method,
        "path": request.url.path,
        "status_code": response.status_code,
        "process_time_ms": round(process_time, 2),
        "client_ip": request.client.host if request.client else None
    }
    
    print(f"API Request: {log_data}")  # Replace with proper logging
    
    return response