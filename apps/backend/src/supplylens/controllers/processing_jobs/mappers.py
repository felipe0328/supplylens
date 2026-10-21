from supplylens.controllers.processing_jobs.types import ProcessingJob as ControllerJob
from supplylens.port.persistence.processing_job import ProcessingJob as PortJob


def map_port_processing_job_to_controller_job(job: PortJob) -> ControllerJob:
    return ControllerJob(
        id=job.id,
        document_uuid=job.document_uuid,
        attempts=job.attempts,
        status=job.status,
        lease_owner=job.lease_owner,
        lease_expires_at=job.lease_expires_at,
        error_code=job.error_code,
        error_message=job.error_message,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )
