import os
from redis import Redis
from rq import Queue, get_current_job
from rq.job import Job
from typing import Dict, Any, Optional
import json
from datetime import datetime
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

# Get Redis URL from environment with fallback
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
logger.info(f"Configured Redis URL: {REDIS_URL.split('@')[0]}@***")

@lru_cache()
def get_redis_connection():
    """Get or create Redis connection"""
    try:
        logger.info("Attempting to connect to Redis...")
        conn = Redis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
            charset="utf-8",
            encoding="utf-8"
        )
        # Test connection
        conn.ping()
        logger.info("Successfully connected to Redis")
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {str(e)}")
        logger.error(f"Redis URL format: {REDIS_URL.split('@')[0]}@***")
        raise

def get_queue():
    """Get or create Queue instance"""
    return Queue('nmkr_support', connection=get_redis_connection())

def process_support_request(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Process the support request in the background"""
    job = get_current_job()
    
    try:
        job.meta['status'] = 'processing'
        job.save_meta()

        # Ensure proper encoding of input data
        sanitized_inputs = {
            'support_request': str(inputs['support_request']),
            'links_data': str(inputs['links_data']),
            'docs_links_data': str(inputs['docs_links_data'])
        }

        from nmkr_support_v4.crew import crew
        result = crew.kickoff(inputs=sanitized_inputs)

        response = {
            'status': 'completed',
            'result': str(result),
            'completed_at': datetime.utcnow().isoformat()
        }
        job.meta.update(response)
        job.save_meta()
        return response

    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        error_response = {
            'status': 'failed',
            'error': str(e),
            'completed_at': datetime.utcnow().isoformat()
        }
        job.meta.update(error_response)
        job.save_meta()
        return error_response

def enqueue_request(inputs: Dict[str, Any]) -> str:
    """Add request to queue and return job ID"""
    try:
        # Ensure all input data is properly encoded
        sanitized_inputs = {
            key: str(value) if isinstance(value, str) else value
            for key, value in inputs.items()
        }
        
        queue = get_queue()
        job = queue.enqueue(
            'nmkr_support_v4.queue_manager.process_support_request',
            args=(sanitized_inputs,),
            job_timeout='1h'
        )
        return job.id
    except Exception as e:
        logger.error(f"Error enqueueing request: {str(e)}")
        raise

def get_job_status(job_id: str) -> Optional[Dict[str, Any]]:
    """Get the status of a job by its ID"""
    try:
        job = Job.fetch(job_id, connection=get_redis_connection())
        if not job:
            return None

        status = {
            'id': job.id,
            'status': job.get_status(),
            'enqueued_at': job.enqueued_at.isoformat() if job.enqueued_at else None,
            'started_at': job.started_at.isoformat() if job.started_at else None,
            'ended_at': job.ended_at.isoformat() if job.ended_at else None,
        }

        if job.is_finished:
            status.update({k: str(v) for k, v in job.meta.items()})
        elif job.is_failed:
            status['error'] = str(job.exc_info)

        return status
    except Exception as e:
        logger.error(f"Error fetching job status: {str(e)}")
        return {
            'id': job_id,
            'status': 'error',
            'error': str(e)
        } 