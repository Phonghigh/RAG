"""Tests for storage operations."""
import pytest
from io import BytesIO
from unittest.mock import Mock, AsyncMock, patch
from apps.shared.storage.client import S3StorageClient, MinIOStorageClient
from apps.shared.config import settings


class TestStorageClient:
    """Test storage client."""
    
    @pytest.mark.asyncio
    async def test_s3_upload_file(self):
        """Test S3 file upload."""
        with patch("apps.shared.storage.client.boto3") as mock_boto3:
            mock_client = Mock()
            mock_boto3.client.return_value = mock_client
            
            client = S3StorageClient()
            file_obj = BytesIO(b"test content")
            
            object_uri = await client.upload_file(
                bucket="test-bucket",
                key="test-key",
                file_obj=file_obj,
            )
            
            assert mock_client.upload_fileobj.called
            assert "test-bucket" in object_uri or "test-key" in object_uri
    
    @pytest.mark.asyncio
    async def test_minio_upload_file(self):
        """Test MinIO file upload."""
        with patch("apps.shared.storage.client.Minio") as mock_minio_class:
            mock_client = Mock()
            mock_client.bucket_exists.return_value = True
            mock_minio_class.return_value = mock_client
            
            client = MinIOStorageClient()
            file_obj = BytesIO(b"test content")
            
            object_uri = await client.upload_file(
                bucket="test-bucket",
                key="test-key",
                file_obj=file_obj,
            )
            
            assert mock_client.put_object.called
            assert "test-bucket" in object_uri or "test-key" in object_uri
    
    @pytest.mark.asyncio
    async def test_get_object_uri(self):
        """Test object URI generation."""
        with patch("apps.shared.storage.client.Minio") as mock_minio_class:
            mock_client = Mock()
            mock_client.bucket_exists.return_value = True
            mock_minio_class.return_value = mock_client
            
            client = MinIOStorageClient()
            uri = client.get_object_uri("test-bucket", "test-key")
            
            assert "test-bucket" in uri
            assert "test-key" in uri

