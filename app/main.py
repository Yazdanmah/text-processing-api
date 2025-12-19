from fastapi import FastAPI
from app.api.routes import router

app = FastAPI(
    title="Text Processing API Pro",
    version="3.0.0",
    description="Commercial-grade text processing API"
)

app.include_router(router)

@app.get("/", tags=["Health"])
def root():
    return {
        "service": "Text Processing API",
        "status": "healthy",
        "version": "3.0.0"
    }
