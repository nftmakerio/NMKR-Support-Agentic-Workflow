import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.append(project_root)

from redis import Redis
from rq import Queue, get_current_job
from rq.job import Job
from typing import Dict, Any, Optional
import json
from datetime import datetime

# Initialize Redis connection using environment variable
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
redis_conn = Redis.from_url(REDIS_URL)
task_queue = Queue('nmkr_support', connection=redis_conn)

def process_support_request(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process the support request in the background
    """
    job = get_current_job()
    
    try:
        # Update job status
        job.meta['status'] = 'processing'
        job.save_meta()

        # Import crew here inside the worker process
        from nmkr_support_v4.crew import crew

        # Execute crew workflow
        result = crew.kickoff(inputs=inputs)

        # Store the result
        response = {
            'status': 'completed',
            'result': str(result),
            'completed_at': datetime.utcnow().isoformat()
        }
        job.meta.update(response)
        job.save_meta()
        
        return response

    except Exception as e:
        error_response = {
            'status': 'failed',
            'error': str(e),
            'completed_at': datetime.utcnow().isoformat()
        }
        job.meta.update(error_response)
        job.save_meta()
        return error_response

def enqueue_request(inputs: Dict[str, Any]) -> str:
    """
    Add request to queue and return job ID
    """
    job = task_queue.enqueue(
        'nmkr_support_v4.queue_manager.process_support_request',
        args=(inputs,),
        job_timeout='1h'
    )
    return job.id

def get_job_status(job_id: str) -> Optional[Dict[str, Any]]:
    """
    Get the status of a job by its ID
    """
    job = Job.fetch(job_id, connection=redis_conn)
    
    if not job:
        return None

    status = {
        'id': job.id,
        'status': job.get_status(),
        'enqueued_at': job.enqueued_at.isoformat() if job.enqueued_at else None,
        'started_at': job.started_at.isoformat() if job.started_at else None,
        'ended_at': job.ended_at.isoformat() if job.ended_at else None,
    }

    # Include result or error if job is finished
    if job.is_finished:
        status.update(job.meta)
    elif job.is_failed:
        status['error'] = str(job.exc_info)

    return status 