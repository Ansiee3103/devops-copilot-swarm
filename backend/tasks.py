from backend.celery_app import celery_app
from backend.database import SessionLocal
from backend.services.deployment_service import DeploymentService
from backend.core.logger import get_logger

logger = get_logger("celery_tasks")

@celery_app.task(name="backend.tasks.run_deployment_pipeline")
def run_deployment_pipeline(deployment_id: int, service_name: str, repo_url: str, changes: str):
    logger.info(f"⏳ Celery worker executing pipeline for deployment #{deployment_id}")
    db = SessionLocal()
    try:
        service = DeploymentService(db)
        service._run_pipeline(deployment_id, service_name, repo_url, changes)
        logger.info(f"✅ Celery worker completed pipeline for deployment #{deployment_id}")
    except Exception as e:
        logger.error(f"❌ Celery worker failed pipeline for deployment #{deployment_id}: {e}")
        raise e
    finally:
        db.close()
