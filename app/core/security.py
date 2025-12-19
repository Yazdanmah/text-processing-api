from fastapi import Header, HTTPException, Request
from app.core.config import API_KEYS

def authenticate(
    request: Request,
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    x_rapidapi_key: str | None = Header(None, alias="X-RapidAPI-Key"),
    x_rapidapi_proxy_secret: str | None = Header(None, alias="X-RapidAPI-Proxy-Secret"),
):
    # RapidAPI
    if x_rapidapi_proxy_secret:
        if not x_rapidapi_key:
            raise HTTPException(403, "Missing RapidAPI key")
        return {"consumer": x_rapidapi_key, "plan": "rapidapi"}

    # Direct API usage
    key_map = dict(k.split(":") for k in API_KEYS.split(",") if ":" in k)

    if not x_api_key or x_api_key not in key_map:
        raise HTTPException(403, "Invalid API key")

    return {"consumer": x_api_key, "plan": key_map[x_api_key]}
