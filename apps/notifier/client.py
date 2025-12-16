"""Google Chat notifier client."""
import logging
from typing import Any, Optional
import httpx
from apps.shared.config import settings

logger = logging.getLogger("app.notifier")


class GoogleChatNotifier:
    """Google Chat notifier client."""
    
    def __init__(
        self,
        webhook_url: Optional[str] = None,
        thread_key: Optional[str] = None,
        notified_users: Optional[str] = None,
    ):
        """Initialize Google Chat notifier."""
        self.webhook_url = webhook_url or settings.google_chat_webhook_url
        self.thread_key = thread_key or settings.google_chat_thread_key
        self.notified_users = notified_users or settings.google_chat_notified_users
        
        if not self.webhook_url:
            raise ValueError("Google Chat webhook URL is required")
    
    def send_message(
        self,
        text: str,
        *,
        thread_key: Optional[str] = None,
        notified_users: Optional[str] = None,
    ) -> dict[str, Any]:
        """Send a text message to Google Chat.
        
        Args:
            text: Message text
            thread_key: Optional thread key for threading
            notified_users: Optional comma-separated list of users to notify
            
        Returns:
            Response from Google Chat API
        """
        payload: dict[str, Any] = {"text": text}
        
        # Use thread key if provided
        use_thread_key = thread_key or self.thread_key
        if use_thread_key:
            payload["thread"] = {"threadKey": use_thread_key}
        
        # Add user mentions if provided
        if notified_users or self.notified_users:
            users = (notified_users or self.notified_users).split(",")
            mentions = [f"<users/{user.strip()}>" for user in users if user.strip()]
            if mentions:
                payload["text"] = f"{' '.join(mentions)} {text}"
        
        logger.info(f"Sending message to Google Chat: {payload}")
        
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(
                    self.webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                return response.json() if response.content else {}
        except httpx.HTTPError as e:
            logger.error(f"Error sending message to Google Chat: {e}")
            raise
    
    def send_card(self, card: dict[str, Any]) -> dict[str, Any]:
        """Send a card message to Google Chat.
        
        Args:
            card: Card payload (Google Chat card format)
            
        Returns:
            Response from Google Chat API
        """
        payload: dict[str, Any] = {"cardsV2": [{"card": card}]}
        
        # Use thread key if available
        if self.thread_key:
            payload["thread"] = {"threadKey": self.thread_key}
        
        logger.info(f"Sending card to Google Chat")
        
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(
                    self.webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                return response.json() if response.content else {}
        except httpx.HTTPError as e:
            logger.error(f"Error sending card to Google Chat: {e}")
            raise

