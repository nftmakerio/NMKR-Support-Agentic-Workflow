from fastapi import FastAPI, HTTPException, Header, Request, Path
from pydantic import BaseModel, Field
from nmkr_support_v4.crew import validate_support_request
from nmkr_support_v4.queue_manager import enqueue_request, get_job_status, get_redis_connection, REDIS_URL
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

# Initialize FastAPI app with enhanced metadata
app = FastAPI(
    title="NMKR Support AI API",
    description="""
    AI-powered support system for NMKR platform. This API provides automated responses to user queries about NMKR's products and services.
    
    ## Features
    * AI-powered support responses
    * Asynchronous processing with job status tracking
    * Plain webhook integration
    * Comprehensive documentation crawling
    
    ## Authentication
    * API requests require appropriate environment variables to be set
    * Webhook endpoints require valid Plain signatures
    """,
    version="1.0.0",
    contact={
        "name": "NMKR Support",
        "url": "https://www.nmkr.io/contact",
        "email": "support@nmkr.io",
    },
    license_info={
        "name": "Private",
        "url": "https://www.nmkr.io/terms",
    },
)

# Webhook secret (should be stored in environment variables in production)
WEBHOOK_SECRET = "your-webhook-secret"

# Request/Response models with enhanced documentation
class SupportRequest(BaseModel):
    """
    Support request input model
    """
    query: str = Field(
        ...,
        description="The support question or query from the user",
        example="How much does it cost to do an Airdrop with NMKR?"
    )
    language: Optional[str] = Field(
        default="en",
        description="Preferred language for the response (ISO 639-1 code)",
        example="en"
    )

class SupportResponse(BaseModel):
    """
    Support request response model
    """
    answer: str = Field(
        ...,
        description="The AI-generated response to the support query"
    )
    success: bool = Field(
        ...,
        description="Indicates if the request was processed successfully"
    )
    error: Optional[str] = Field(
        None,
        description="Error message if the request failed"
    )

class WebhookEvent(BaseModel):
    """
    Plain webhook event model
    """
    id: str = Field(..., description="Unique identifier for the webhook event")
    type: str = Field(..., description="Type of the webhook event")
    webhookMetadata: Dict[str, Any] = Field(..., description="Metadata associated with the webhook")
    timestamp: str = Field(..., description="Timestamp of the event")
    workspaceId: str = Field(..., description="Plain workspace identifier")
    payload: Dict[str, Any] = Field(..., description="Event payload containing the message")

class JobResponse(BaseModel):
    """
    Job creation response model
    """
    job_id: str = Field(..., description="Unique identifier for the created job")
    status: str = Field(..., description="Initial status of the job")

class JobStatus(BaseModel):
    """
    Job status response model
    """
    id: str = Field(..., description="Job identifier")
    status: str = Field(..., description="Current status of the job")
    result: Optional[str] = Field(None, description="Job result if completed")
    error: Optional[str] = Field(None, description="Error message if job failed")
    enqueued_at: Optional[str] = Field(None, description="Timestamp when job was queued")
    started_at: Optional[str] = Field(None, description="Timestamp when job started")
    ended_at: Optional[str] = Field(None, description="Timestamp when job completed")

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

@app.post("/api/webhook",
    status_code=200,
    tags=["Webhooks"],
    summary="Handle Plain webhook events",
    description="""
    Process incoming webhook events from Plain. Validates the webhook signature
    and processes support requests from the webhook payload.
    """
)
async def handle_webhook(
    request: Request,
    event: WebhookEvent,
    plain_workspace_id: str = Header(..., alias="Plain-Workspace-Id"),
    plain_event_type: str = Header(..., alias="Plain-Event-Type"),
    plain_event_id: str = Header(..., alias="Plain-Event-Id")
):
    """
    Handle incoming webhook events from Plain.

    Args:
        request (Request): The raw HTTP request
        event (WebhookEvent): The webhook event data
        plain_workspace_id (str): Plain workspace identifier
        plain_event_type (str): Type of the webhook event
        plain_event_id (str): Unique identifier for the event

    Returns:
        dict: Processing status and job ID if applicable

    Raises:
        HTTPException: If the webhook signature is invalid
    """
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

@app.post("/api/support", 
    response_model=JobResponse,
    tags=["Support"],
    summary="Create a new support request",
    description="""
    Submit a support request for AI processing. The request is processed asynchronously,
    and a job ID is returned for tracking the status.
    """
)
async def handle_support_request(request: SupportRequest):
    """
    Create a new support request for AI processing.

    Args:
        request (SupportRequest): The support request containing the query

    Returns:
        JobResponse: Contains the job ID and initial status

    Raises:
        HTTPException: If the request is invalid or processing fails
    """
    try:
        if not validate_support_request(request.query):
            raise HTTPException(status_code=400, detail="Invalid support request")

        crew = get_crew()
        inputs = {
            'support_request': request.query,
            'links_data': crew.tasks[2].description,
            'docs_links_data': crew.tasks[3].description
        }

        job_id = enqueue_request(inputs)

        return JobResponse(
            job_id=job_id,
            status="queued"
        )

    except Exception as e:
        logger.error(f"Error processing support request: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/support/status/{job_id}",
    response_model=JobStatus,
    tags=["Support"],
    summary="Get support request status",
    description="Check the status and result of a previously submitted support request."
)
async def get_support_request_status(
    job_id: str = Path(..., description="The ID of the job to check")
):
    """
    Get the current status of a support request job.

    Args:
        job_id (str): The unique identifier of the job

    Returns:
        JobStatus: Current status and result of the job

    Raises:
        HTTPException: If the job is not found
    """
    status = get_job_status(job_id)
    if not status:
        raise HTTPException(status_code=404, detail="Job not found")
    return status

# Get port from environment variable with fallback
PORT = int(os.getenv('PORT', 8080))

@app.get("/health",
    tags=["System"],
    summary="System health check",
    description="Check the health status of the API and its dependencies."
)
async def health_check():
    """
    Check the health status of the system and its components.

    Returns:
        dict: Health status of all system components
    """
    try:
        # Get Redis connection
        redis_conn = get_redis_connection()
        redis_info = redis_conn.info()
        redis_status = "healthy" if redis_info else "unhealthy"
        
        status = {
            "status": "healthy" if redis_status == "healthy" else "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                "api": "healthy",
                "redis": redis_status
            },
            "port": PORT,
            "redis_url": REDIS_URL.replace(REDIS_URL.split('@')[-1], '***') if '@' in REDIS_URL else "redis://***",
            "environment": {
                "has_redis_url": "REDIS_URL" in os.environ,
                "has_openai_key": "OPENAI_API_KEY" in os.environ,
                "has_webhook_secret": "WEBHOOK_SECRET" in os.environ,
            }
        }
        return status
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
            "redis_url": REDIS_URL.replace(REDIS_URL.split('@')[-1], '***') if '@' in REDIS_URL else "redis://***",
            "environment": {
                "has_redis_url": "REDIS_URL" in os.environ,
                "has_openai_key": "OPENAI_API_KEY" in os.environ,
                "has_webhook_secret": "WEBHOOK_SECRET" in os.environ,
            }
        }

@app.get("/redis-status",
    tags=["System"],
    summary="Redis connection status",
    description="Detailed status check of the Redis connection and configuration."
)
async def redis_status():
    """
    Get detailed information about the Redis connection status.

    Returns:
        dict: Detailed Redis connection and configuration status
    """
    try:
        # Get Redis connection
        redis_conn = get_redis_connection()
        info = redis_conn.info()
        
        return {
            "status": "connected",
            "redis_info": {
                "version": info.get("redis_version"),
                "connected_clients": info.get("connected_clients"),
                "used_memory_human": info.get("used_memory_human"),
                "total_connections_received": info.get("total_connections_received"),
            },
            "redis_url": REDIS_URL.replace(REDIS_URL.split('@')[-1], '***') if '@' in REDIS_URL else "redis://***",
            "environment": {
                "has_redis_url": "REDIS_URL" in os.environ,
                "redis_url_value": os.environ.get("REDIS_URL", "not_set")[:10] + "..." if os.environ.get("REDIS_URL") else "not_set"
            }
        }
    except Exception as e:
        logger.error(f"Redis status check failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "environment": {
                "has_redis_url": "REDIS_URL" in os.environ,
                "redis_url_value": os.environ.get("REDIS_URL", "not_set")[:10] + "..." if os.environ.get("REDIS_URL") else "not_set"
            }
        }

# Add tags metadata
app.openapi_tags = [
    {
        "name": "Support",
        "description": "Support request operations including creation and status checking",
    },
    {
        "name": "Webhooks",
        "description": "Plain webhook integration endpoints",
    },
    {
        "name": "System",
        "description": "System health and status monitoring endpoints",
    },
]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT) 