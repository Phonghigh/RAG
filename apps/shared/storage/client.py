"""Storage client abstraction for S3/MinIO."""
from abc import ABC, abstractmethod
from typing import Optional, BinaryIO
import boto3
from botocore.exceptions import ClientError
from minio import Minio
from minio.error import S3Error
from apps.shared.config import settings


class StorageClient(ABC):
    """Abstract storage client interface."""
    
    @abstractmethod
    async def upload_file(
        self,
        bucket: str,
        key: str,
        file_obj: BinaryIO,
        content_type: Optional[str] = None,
    ) -> str:
        """Upload a file and return object URI."""
        pass
    
    @abstractmethod
    async def download_file(self, bucket: str, key: str) -> bytes:
        """Download a file and return bytes."""
        pass
    
    @abstractmethod
    async def delete_file(self, bucket: str, key: str) -> None:
        """Delete a file."""
        pass
    
    @abstractmethod
    async def file_exists(self, bucket: str, key: str) -> bool:
        """Check if file exists."""
        pass
    
    @abstractmethod
    def get_object_uri(self, bucket: str, key: str) -> str:
        """Get object URI for storage."""
        pass


class S3StorageClient(StorageClient):
    """S3-compatible storage client."""
    
    def __init__(self):
        """Initialize S3 client."""
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
            use_ssl=settings.s3_use_ssl,
        )
        self.bucket_name = settings.s3_bucket_name
        self._ensure_bucket_exists()
    
    def _ensure_bucket_exists(self):
        """Ensure bucket exists, create if not."""
        try:
            self.client.head_bucket(Bucket=self.bucket_name)
        except ClientError:
            self.client.create_bucket(Bucket=self.bucket_name)
    
    async def upload_file(
        self,
        bucket: str,
        key: str,
        file_obj: BinaryIO,
        content_type: Optional[str] = None,
    ) -> str:
        """Upload a file to S3."""
        try:
            extra_args = {}
            if content_type:
                extra_args["ContentType"] = content_type
            
            self.client.upload_fileobj(
                file_obj,
                bucket,
                key,
                ExtraArgs=extra_args,
            )
            return self.get_object_uri(bucket, key)
        except ClientError as e:
            raise RuntimeError(f"Failed to upload file: {e}") from e
    
    async def download_file(self, bucket: str, key: str) -> bytes:
        """Download a file from S3."""
        try:
            response = self.client.get_object(Bucket=bucket, Key=key)
            return response["Body"].read()
        except ClientError as e:
            raise RuntimeError(f"Failed to download file: {e}") from e
    
    async def delete_file(self, bucket: str, key: str) -> None:
        """Delete a file from S3."""
        try:
            self.client.delete_object(Bucket=bucket, Key=key)
        except ClientError as e:
            raise RuntimeError(f"Failed to delete file: {e}") from e
    
    async def file_exists(self, bucket: str, key: str) -> bool:
        """Check if file exists in S3."""
        try:
            self.client.head_object(Bucket=bucket, Key=key)
            return True
        except ClientError:
            return False
    
    def get_object_uri(self, bucket: str, key: str) -> str:
        """Get S3 object URI."""
        if settings.s3_endpoint_url:
            return f"{settings.s3_endpoint_url}/{bucket}/{key}"
        return f"s3://{bucket}/{key}"


class MinIOStorageClient(StorageClient):
    """MinIO storage client."""
    
    def __init__(self):
        """Initialize MinIO client."""
        endpoint = settings.s3_endpoint_url or "localhost:9000"
        secure = settings.s3_use_ssl
        
        # Parse endpoint
        if "://" in endpoint:
            endpoint = endpoint.split("://")[1]
        
        self.client = Minio(
            endpoint,
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
            secure=secure,
        )
        self.bucket_name = settings.s3_bucket_name
        self._ensure_bucket_exists()
    
    def _ensure_bucket_exists(self):
        """Ensure bucket exists, create if not."""
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
        except S3Error as e:
            raise RuntimeError(f"Failed to ensure bucket exists: {e}") from e
    
    async def upload_file(
        self,
        bucket: str,
        key: str,
        file_obj: BinaryIO,
        content_type: Optional[str] = None,
    ) -> str:
        """Upload a file to MinIO."""
        try:
            file_obj.seek(0)
            length = file_obj.seek(0, 2)
            file_obj.seek(0)
            
            self.client.put_object(
                bucket,
                key,
                file_obj,
                length=length,
                content_type=content_type or "application/octet-stream",
            )
            return self.get_object_uri(bucket, key)
        except S3Error as e:
            raise RuntimeError(f"Failed to upload file: {e}") from e
    
    async def download_file(self, bucket: str, key: str) -> bytes:
        """Download a file from MinIO."""
        try:
            response = self.client.get_object(bucket, key)
            return response.read()
        except S3Error as e:
            raise RuntimeError(f"Failed to download file: {e}") from e
    
    async def delete_file(self, bucket: str, key: str) -> None:
        """Delete a file from MinIO."""
        try:
            self.client.remove_object(bucket, key)
        except S3Error as e:
            raise RuntimeError(f"Failed to delete file: {e}") from e
    
    async def file_exists(self, bucket: str, key: str) -> bool:
        """Check if file exists in MinIO."""
        try:
            self.client.stat_object(bucket, key)
            return True
        except S3Error:
            return False
    
    def get_object_uri(self, bucket: str, key: str) -> str:
        """Get MinIO object URI."""
        endpoint = settings.s3_endpoint_url or "http://localhost:9000"
        if "://" not in endpoint:
            endpoint = f"http://{endpoint}"
        return f"{endpoint}/{bucket}/{key}"


def get_storage_client() -> StorageClient:
    """Get storage client based on configuration."""
    if settings.storage_type == "minio":
        return MinIOStorageClient()
    elif settings.storage_type == "s3":
        return S3StorageClient()
    else:
        raise ValueError(f"Unknown storage type: {settings.storage_type}")

