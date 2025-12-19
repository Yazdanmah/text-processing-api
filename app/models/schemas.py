from pydantic import BaseModel, Field
from typing import Optional, Dict, List

class ErrorDetail(BaseModel):
    code: str
    message: str

class APIResponse(BaseModel):
    success: bool
    data: Optional[Dict] = None
    error: Optional[ErrorDetail] = None

class BatchRequest(BaseModel):
    texts: List[str] = Field(..., min_items=1)
    action: str
