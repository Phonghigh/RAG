"""Application configuration using Pydantic Settings."""
import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Application settings."""
    
    model_config = SettingsConfigDict(
        env_file="configs/.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # App settings
    app_name: str = Field(default="RCA-RAG", description="Application name")
    app_env: str = Field(default="development", description="Environment")
    app_host: str = Field(default="0.0.0.0", description="Host to bind")
    app_port: int = Field(default=8080, description="Port to bind")
    
    # Database
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/rca_rag",
        description="Database connection URL"
    )
    database_echo: bool = Field(default=False, description="Echo SQL queries")
    
    # Message Queue
    mq_type: str = Field(default="redis", description="MQ type: redis, kafka, rabbitmq")
    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis URL")
    kafka_bootstrap_servers: str = Field(
        default="localhost:9094",
        description="Kafka bootstrap servers"
    )
    kafka_topic_prefix: str = Field(default="rca-rag", description="Kafka topic prefix")
    rabbitmq_url: str = Field(
        default="amqp://admin:admin@localhost:5672/",
        description="RabbitMQ URL"
    )
    
    # Storage (S3/MinIO)
    storage_type: str = Field(default="minio", description="Storage type: s3, minio")
    s3_endpoint_url: Optional[str] = Field(default=None, description="S3 endpoint URL")
    s3_access_key: str = Field(default="minioadmin", description="S3 access key")
    s3_secret_key: str = Field(default="minioadmin", description="S3 secret key")
    s3_bucket_name: str = Field(default="rca-rag", description="S3 bucket name")
    s3_region: str = Field(default="us-east-1", description="S3 region")
    s3_use_ssl: bool = Field(default=False, description="Use SSL for S3")
    
    # Google Chat
    google_chat_webhook_url: Optional[str] = Field(
        default=None,
        description="Google Chat webhook URL"
    )
    google_chat_thread_key: Optional[str] = Field(
        default=None,
        description="Google Chat thread key"
    )
    google_chat_notified_users: str = Field(
        default="",
        description="Comma-separated list of users to notify"
    )
    
    # GitHub
    github_webhook_secret: str = Field(
        default="",
        description="GitHub webhook secret for signature verification"
    )
    github_trusted_ua_prefix: str = Field(
        default="GitHub-Hookshot/",
        description="Trusted User-Agent prefix"
    )
    github_app_id: Optional[str] = Field(default=None, description="GitHub App ID")
    github_app_private_key: Optional[str] = Field(
        default=None,
        description="GitHub App private key (PEM)"
    )
    
    # Retention
    retention_days: int = Field(default=90, description="Days to retain raw diffs")
    
    # Observability
    log_level: str = Field(default="INFO", description="Logging level")
    metrics_enabled: bool = Field(default=True, description="Enable Prometheus metrics")
    
    # Security
    jwt_secret_key: str = Field(
        default="change-me-in-production",
        description="JWT secret key"
    )
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_access_token_expire_minutes: int = Field(
        default=30,
        description="JWT access token expiration in minutes"
    )
    
    # Air-gapped
    allow_external_requests: bool = Field(
        default=False,
        description="Allow external HTTP requests (for air-gapped environments)"
    )

    # Analysis & RAG
    embedding_model_name: str = Field(
        default="all-MiniLM-L6-v2",
        description="Embedding model name for RAG (sentence-transformers compatible)"
    )
    rag_top_k: int = Field(default=5, description="Default number of chunks to retrieve for RAG queries")
    rules_config_path: Optional[str] = Field(
        default="configs/rules.yaml",
        description="Path to rules YAML configuration file"
    )
    cve_db_path: Optional[str] = Field(
        default=None,
        description="Path to CVE database file (JSON or CSV)"
    )
    indexing_enabled: bool = Field(
        default=True,
        description="Enable automatic indexing after analysis completes"
    )
    analysis_timeout: int = Field(
        default=300,
        description="Analysis timeout in seconds for long-running analysis"
    )


# Global settings instance
settings = Settings()
