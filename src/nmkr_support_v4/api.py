from fastapi import FastAPI, HTTPException, Header, Request
from pydantic import BaseModel
# Update the import path
from nmkr_support_v4.crew import validate_support_request
from nmkr_support_v4.queue_manager import enqueue_request, get_job_status
import logging
from typing import Optional, Dict, Any
import hmac
import hashlib
import json
from datetime import datetime
import redis
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="NMKR Support API",
    description="API for handling NMKR support requests using AI agents",
    version="1.0.0"
)

# Webhook secret (should be stored in environment variables in production)
WEBHOOK_SECRET = "your-webhook-secret"

# Request/Response models
class SupportRequest(BaseModel):
    query: str
    language: Optional[str] = "en"

class SupportResponse(BaseModel):
    answer: str
    success: bool
    error: Optional[str] = None

class WebhookEvent(BaseModel):
    id: str
    type: str
    webhookMetadata: Dict[str, Any]
    timestamp: str
    workspaceId: str
    payload: Dict[str, Any]

class JobResponse(BaseModel):
    job_id: str
    status: str

class JobStatus(BaseModel):
    id: str
    status: str
    result: Optional[str] = None
    error: Optional[str] = None
    enqueued_at: Optional[str] = None
    started_at: Optional[str] = None
    ended_at: Optional[str] = None

def get_crew():
    """Lazy loading of crew to prevent initialization at startup"""
    from nmkr_support_v4.crew import crew
    return crew

async def verify_webhook_signature(request: Request) -> bool:
    body = await request.body()
    signature = request.headers.get("Plain-Signature")
    if not signature:
        return False
    
    expected_signature = hmac.new(
        WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected_signature)

@app.post("/api/webhook", status_code=200)
async def handle_webhook(
    request: Request,
    event: WebhookEvent,
    plain_workspace_id: str = Header(..., alias="Plain-Workspace-Id"),
    plain_event_type: str = Header(..., alias="Plain-Event-Type"),
    plain_event_id: str = Header(..., alias="Plain-Event-Id")
):
    if not await verify_webhook_signature(request):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    try:
        logger.info(f"Received webhook event: {plain_event_type} with ID: {plain_event_id}")
        
        support_query = event.payload.get("message", {}).get("content", "")
        
        if not support_query:
            return {"status": "success", "message": "No support query found in payload"}

        crew = get_crew()
        inputs = {
            'support_request': support_query,
            'links_data': crew.tasks[2].description,
            'docs_links_data': crew.tasks[3].description
        }

        # Only pass the inputs to the queue
        job_id = enqueue_request(inputs)
        
        return {
            "status": "queued",
            "job_id": job_id
        }

    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

@app.post("/api/support", response_model=JobResponse)
async def handle_support_request(request: SupportRequest):
    try:
        if not validate_support_request(request.query):
            raise HTTPException(status_code=400, detail="Invalid support request")

        crew = get_crew()
        inputs = {
            'support_request': request.query,
            'links_data': crew.tasks[2].description,
            'docs_links_data': crew.tasks[3].description
        }

        # Only pass the inputs to the queue, not the crew object
        job_id = enqueue_request(inputs)

        return JobResponse(
            job_id=job_id,
            status="queued"
        )

    except Exception as e:
        logger.error(f"Error processing support request: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/support/status/{job_id}", response_model=JobStatus)
async def get_support_request_status(job_id: str):
    status = get_job_status(job_id)
    if not status:
        raise HTTPException(status_code=404, detail="Job not found")
    return status

# Get port from environment variable with fallback
PORT = int(os.getenv('PORT', 8080))

@app.get("/health")
async def health_check():
    """
    Health check endpoint that verifies all required services are running
    """
    try:
        # Check Redis connection
        redis_info = redis_conn.info()
        
        # Basic application status
        status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                "api": "healthy",
                "redis": "healthy" if redis_info else "unhealthy"
            },
            "port": PORT
        }
        return status
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }, 500

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT) 