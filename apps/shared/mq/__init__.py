"""Message queue package."""
from apps.shared.mq.client import MQClient, get_mq_client

__all__ = ["MQClient", "get_mq_client"]

