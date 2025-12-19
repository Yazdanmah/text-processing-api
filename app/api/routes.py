from fastapi import APIRouter, Query, Depends, HTTPException
from datetime import datetime
from app.core.rate_limit import rate_limit
from app.core.config import PLANS
from app.models.schemas import APIResponse, BatchRequest
from app.services import text_service

router = APIRouter(tags=["Text"])

def check_feature(plan: str, feature: str):
    if feature not in PLANS[plan]["features"]:
        raise HTTPException(403, "Feature not available")

@router.get("/text", response_model=APIResponse)
def process_text(
    text: str = Query(..., min_length=1, max_length=5000),
    action: str = Query(...),
    ctx=Depends(rate_limit)
):
    action = action.lower()
    check_feature(ctx["plan"], action)

    if action == "clean":
        result = text_service.clean_text(text)
    elif action == "lower":
        result = text.lower()
    elif action == "upper":
        result = text.upper()
    elif action == "slug":
        result = text_service.slugify(text)
    elif action == "stats":
        result = text_service.text_stats(text)
    else:
        raise HTTPException(400, "Invalid action")

    return APIResponse(
        success=True,
        data={
            "action": action,
            "result": result,
            "processed_at": datetime.utcnow().isoformat()
        }
    )

@router.post("/batch", response_model=APIResponse)
def batch_process(
    payload: BatchRequest,
    ctx=Depends(rate_limit)
):
    check_feature(ctx["plan"], "batch")
    limit = PLANS[ctx["plan"]]["batch_limit"]

    if len(payload.texts) > limit:
        raise HTTPException(403, "Batch limit exceeded")

    results = []
    for text in payload.texts:
        if payload.action == "clean":
            processed = text_service.clean_text(text)
        elif payload.action == "lower":
            processed = text.lower()
        elif payload.action == "upper":
            processed = text.upper()
        elif payload.action == "slug":
            processed = text_service.slugify(text)
        elif payload.action == "stats":
            processed = text_service.text_stats(text)
        else:
            raise HTTPException(400, "Invalid action")

        results.append({"original": text, "processed": processed})

    return APIResponse(success=True, data={"total": len(results), "results": results})
