import os
from datetime import datetime, UTC
from dotenv import load_dotenv
from google.cloud import storage_transfer
from google.oauth2 import service_account

def create_one_time_aws_transfer(
    project_id: str,
    description: str,
    source_bucket: str,
    aws_access_key_id: str,
    aws_secret_access_key: str,
    sink_bucket: str,
):
    """Creates a one-time transfer job from Amazon S3 to Google Cloud
    Storage."""
    file_path = os.getenv("GOOGLE_CREDENTIALS")
    credentials = service_account.Credentials.from_service_account_file(file_path)
    client = storage_transfer.StorageTransferServiceClient(credentials=credentials)

    # The ID of the Google Cloud Platform Project that owns the job
    project_id = project_id

    # A useful description for your transfer job
    description = description

    # AWS S3 source bucket name
    source_bucket = source_bucket

    # AWS Access Key ID
    aws_access_key_id = aws_access_key_id

    # AWS Secret Access Key
    aws_secret_access_key = aws_secret_access_key

    # Google Cloud Storage destination bucket name
    sink_bucket = sink_bucket

    now = datetime.now(UTC)
    # Setting the start date and the end date as
    # the same time creates a one-time transfer
    one_time_schedule = {"day": now.day, "month": now.month, "year": now.year}

    transfer_job_request = storage_transfer.CreateTransferJobRequest(
        {
            "transfer_job": {
                "project_id": project_id,
                "description": description,
                "status": storage_transfer.TransferJob.Status.ENABLED,
                "schedule": {
                    "schedule_start_date": one_time_schedule,
                    "schedule_end_date": one_time_schedule,
                },
                "transfer_spec": {
                    "aws_s3_data_source": {
                        "bucket_name": source_bucket,
                        "aws_access_key": {
                            "access_key_id": aws_access_key_id,
                            "secret_access_key": aws_secret_access_key,
                        },
                    },
                    "gcs_data_sink": {
                        "bucket_name": sink_bucket,
                    },
                },
            }
        }
    )

    result = client.create_transfer_job(transfer_job_request)
    print(f"Created transferJob: {result.name}")

if __name__ == "__main__":
    load_dotenv()

    # The ID of the Google Cloud Platform Project that owns the job
    project_id = os.getenv("GOOGLE_PROJECT_ID")

    # A useful description for your transfer job
    description = 'Test Transfer Job for AWS to GCS'

    # AWS S3 source bucket name
    source_bucket = os.getenv("AWS_SOURCE_BUCKET")

    # AWS Access Key ID
    aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")

    # AWS Secret Access Key
    aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")

    # Google Cloud Storage destination bucket name
    sink_bucket = os.getenv("GOOGLE_LANDING_BUCKET")

    create_one_time_aws_transfer(
        project_id,
        description,
        source_bucket,
        aws_access_key_id,
        aws_secret_access_key,
        sink_bucket
    )