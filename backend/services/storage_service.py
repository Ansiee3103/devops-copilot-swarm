import boto3
import os
from backend.core.logger import get_logger

logger = get_logger("storage")

class StorageService:
    def __init__(self):
        self.s3 = boto3.client("s3", region_name=os.getenv("AWS_REGION", "ap-south-1"))
        self.bucket = os.getenv("S3_BUCKET", "devops-swarm-outputs")

    def upload_generated_files(self, service_name: str, deployment_id: int) -> dict:
        """Upload generated configs to S3"""
        output_dir = f"outputs/{service_name}"
        uploaded = []

        for filename in ["Dockerfile", "k8s-manifest.yaml", "pipeline.yml"]:
            local_path = f"{output_dir}/{filename}"
            if not os.path.exists(local_path):
                continue

            s3_key = f"deployments/{deployment_id}/{service_name}/{filename}"
            try:
                self.s3.upload_file(local_path, self.bucket, s3_key)
                url = f"https://{self.bucket}.s3.ap-south-1.amazonaws.com/{s3_key}"
                uploaded.append({"file": filename, "url": url})
                logger.info(f"✅ Uploaded to S3: {s3_key}")
            except Exception as e:
                logger.warning(f"S3 upload failed for {filename}: {e}")

        return {"uploaded": uploaded}

    def get_download_url(self, s3_key: str, expiry: int = 3600) -> str:
        """Generate presigned download URL"""
        return self.s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": s3_key},
            ExpiresIn=expiry
        )

storage_service = StorageService()
