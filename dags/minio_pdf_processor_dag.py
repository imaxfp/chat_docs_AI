import json
import logging
import requests
from functools import lru_cache
from datetime import datetime
from typing import List, Set, Optional
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from minio import Minio

# Configure logging
logger = logging.getLogger("airflow.task")

# Configuration
MINIO_ENDPOINT = "minio:9000"
MINIO_ACCESS_KEY = "minioadmin"
MINIO_SECRET_KEY = "minioadmin"
EMBEDDING_SERVICE_URL = "http://extractor-typin-pdf-microservice:8000/process"
POSTGRES_CONN_ID = "PDF_DB"

# --------------------------------------------------------------------------
# PRIVATE SQL HELPERS For file status processing (KISS: Keep It Simple, Secure, and Separated)
# --------------------------------------------------------------------------

def _get_seen_files(hook: PostgresHook, bucket: str) -> Set[str]:
    """Fetch filenames already in registry for this bucket."""
    query = "SELECT filename FROM airflow_file_registry WHERE bucket = %s"
    records = hook.get_records(query, parameters=(bucket,))
    return {row[0] for row in records}

def _get_failed_files(hook: PostgresHook, bucket: str) -> List[str]:
    """Fetch filenames with status 'failed' for retry."""
    query = "SELECT filename FROM airflow_file_registry WHERE bucket = %s AND status = 'failed'"
    records = hook.get_records(query, parameters=(bucket,))
    return [row[0] for row in records]

def _register_new_files(hook: PostgresHook, bucket: str, files: List[str]):
    """
    Insert new files into registry as 'pending'.
    The 'pending' status acts as a soft-lock to ensure that even if multiple 
    DAG runs overlap, they see the file as 'registered' and avoid duplicates.
    """
    for file_name in files:
        hook.run(
            "INSERT INTO airflow_file_registry (bucket, filename, status) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            parameters=(bucket, file_name, 'pending')
        )
        logger.info(f"Registered: [{bucket}] {file_name} (pending)")

def _update_file_status(hook: PostgresHook, bucket: str, filename: str, status: str, error: Optional[str] = None):
    """
    Update file processing status and log errors if they occur.
    
    CRASH LOGIC & STATUS RESOLVING:
    - If processing crashes (timeout, network, service down), the status is caught in the 
      task's try-except block and updated to 'failed'.
    - ROBUSTNESS: We add a status check to the UPDATE query to ensure we never regress 
      a 'processed' file back to 'failed' (e.g. if a delayed retry run finishes after 
       a successful run).
    """
    query = """
        UPDATE airflow_file_registry 
        SET status = %s, error_message = %s, processed_at = CURRENT_TIMESTAMP 
        WHERE bucket = %s AND filename = %s
        AND (status != 'processed' OR %s = 'processed')
    """
    hook.run(query, parameters=(status, error, bucket, filename, status))
    logger.info(f"Updated: [{bucket}] {filename} -> status: {status}")

# --------------------------------------------------------------------------
# PRIVATE MINIO HELPERS
# --------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _get_minio_client() -> Minio:
    """
    Initialize and return a MinIO client.
    
    PERFORMANCE NOTE: We create the client inside this helper rather than at 
    the top-level module scope. This prevents the Airflow Scheduler from 
    creating unnecessary connections every time it parses the DAG file.
    """
    return Minio(
        MINIO_ENDPOINT, 
        access_key=MINIO_ACCESS_KEY, 
        secret_key=MINIO_SECRET_KEY, 
        secure=False
    )

# --------------------------------------------------------------------------
# DAG TASKS
# --------------------------------------------------------------------------

def list_minio_buckets():
    """List all available buckets from MinIO."""
    try:
        client = _get_minio_client()
        buckets = client.list_buckets()
        bucket_names = [b.name for b in buckets]
        logger.info(f"Found buckets: {bucket_names}")
        return bucket_names
    except Exception as e:
        logger.error(f"Failed to list MinIO buckets: {e}")
        raise

def list_pdf_files(ti):
    """List all .pdf files from all discovered MinIO buckets."""
    try:
        buckets = ti.xcom_pull(task_ids="list_minio_buckets")
        if not buckets:
            logger.info("No buckets found to process.")
            return []

        client = _get_minio_client()
        all_pdf_objects = [] # List of {"bucket": str, "filename": str}

        for bucket in buckets:
            logger.info(f"Scanning bucket: {bucket}")
            objects = client.list_objects(bucket, recursive=True)
            for obj in objects:
                if obj.object_name.lower().endswith('.pdf'):
                    all_pdf_objects.append({"bucket": bucket, "filename": obj.object_name})
        
        logger.info(f"Total PDFs found: {len(all_pdf_objects)}")
        return all_pdf_objects
    except Exception as e:
        logger.error(f"MinIO PDF listing failed: {e}")
        raise

def filter_new_pdf_files(ti):
    """
    Filter files into a processing queue (New + Failed) for all buckets.
    """
    try:
        all_pdfs = ti.xcom_pull(task_ids="list_pdf_files")
        if not all_pdfs: return []

        hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)
        queue = []
        
        # Group by bucket to minimize DB queries if needed, 
        # but for simplicity we'll just process the discovery list.
        buckets_in_discovery = set(item["bucket"] for item in all_pdfs)
        
        for bucket in buckets_in_discovery:
            # 1. Discovery in this bucket
            files_in_this_bucket = [i["filename"] for i in all_pdfs if i["bucket"] == bucket]
            seen = _get_seen_files(hook, bucket)
            
            # Register brand new files
            new_files = [f for f in files_in_this_bucket if f not in seen]
            if new_files:
                _register_new_files(hook, bucket, new_files)
            
            # 2. Collect files that need processing (Pending/New + Failed)
            failed = _get_failed_files(hook, bucket)
            
            # The queue contains items that are either:
            # - Brand new (just registered as pending)
            # - Previously registered but still 'pending' or marked as 'failed'
            # We add them to the unified processing queue.
            for file_name in set(new_files + failed):
                queue.append({"bucket": bucket, "filename": file_name})
        
        logger.info(f"Processing queue constructed with {len(queue)} items.")
        return queue
    except Exception as e:
        logger.error(f"Filtering logic failed: {e}")
        raise

def send_minio_pdf_links(ti):
    """
    Process queue via Embedding API and update SQL registry.
    """
    queue = ti.xcom_pull(task_ids="filter_new_pdf_files")
    if not queue: 
        logger.info("Nothing to process.")
        return

    hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)
    
    for item in queue:
        bucket = item["bucket"]
        file_name = item["filename"]
        try:
            logger.info(f"Submitting: [{bucket}] {file_name}")
            # The API expects bucket/path format
            payload = {"file_path": f"{bucket}/{file_name}"}
            resp = requests.post(EMBEDDING_SERVICE_URL, json=payload, timeout=60)
            
            if resp.status_code == 200:
                _update_file_status(hook, bucket, file_name, 'processed')
            else:
                _update_file_status(hook, bucket, file_name, 'failed', resp.text[:255])
        except Exception as e:
            _update_file_status(hook, bucket, file_name, 'failed', f"Crash: {str(e)[:255]}")

# --------------------------------------------------------------------------
# DAG DEFINITION
# --------------------------------------------------------------------------

with DAG(
    dag_id="minio_pdf_processor_dag",
    start_date=datetime(2024, 1, 1),
    schedule="* * * * *",
    catchup=False,
    tags=["minio", "embedding", "postgres", "multibucket"],
) as dag:

    buckets_task = PythonOperator(task_id="list_minio_buckets", python_callable=list_minio_buckets)
    list_task = PythonOperator(task_id="list_pdf_files", python_callable=list_pdf_files)
    filter_task = PythonOperator(task_id="filter_new_pdf_files", python_callable=filter_new_pdf_files)
    send_task = PythonOperator(task_id="send_minio_pdf_links", python_callable=send_minio_pdf_links)

    buckets_task >> list_task >> filter_task >> send_task
