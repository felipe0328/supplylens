import os

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

BUCKET_NAME: str = os.getenv("S3_BUCKET_NAME")
ALLOWED_ORIGINS: list = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]

s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("S3_ACCESS_KEY"),
    aws_secret_access_key=os.getenv("S3_SECRET_KEY"),
    endpoint_url=os.getenv("S3_ENDPOINT"),
    region_name=os.getenv("S3_REGION", "us-east-1"),
)


class CreationException(Exception):
    """Raised when the S3 bucket cannot be created."""


try:
    s3.head_bucket(Bucket=BUCKET_NAME)
except ClientError as e:
    error_code = e.response.get("Error", {}).get("Code")
    status_code = e.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
    if status_code == 404 or error_code in {"404", "NoSuchBucket", "NotFound"}:
        s3.create_bucket(Bucket=BUCKET_NAME)
    else:
        raise CreationException(
            f"Failed to create or access S3 bucket {BUCKET_NAME!r}: {e}"
        ) from e

s3.put_bucket_cors(
    Bucket=BUCKET_NAME,
    CORSConfiguration={
        "CORSRules": [
            {
                "AllowedHeaders": ["*"],
                "AllowedMethods": ["GET", "PUT", "HEAD"],
                "AllowedOrigins": ALLOWED_ORIGINS,
                "ExposeHeaders": ["ETag"],
                "MaxAgeSeconds": 3000,
            }
        ]
    },
)

print(f"Initialized S3 bucket: {BUCKET_NAME!r}")
