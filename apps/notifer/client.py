from ast import Dict
from typing import Any
import logging
from typing import Optional
from apps.shared.config import settings
from json import dumps
from httplib2 import Http

logger = logging.getLogger("app.notifer")

class GooogleChatNotifier:
    def __init__(self, webhook_url: str, thread_key: str, notified_users: str):
        self.webhook_url = webhook_url
        self.thread_key = thread_key
        self.notified_users = notified_users

    def send_message(self,text: str, *,thread_key: Optional[str] = None, notified_users: Optional[str] = None):
        """Send a message to Google Chat

        Args:
            text (str): _description_
            thread_key (Optional[str], optional): _description_. Defaults to None.
            notified_users (Optional[str], optional): _description_. Defaults to None.
        """

        #build payload
        payload: Dict[str, Any] = {
            "text": text
        }
        message_headers: Dict[str, Any] = {
            "Content-Type": "application/json",
            "charset": "utf-8"
        }
        #use thread key if provided
        use_thread_key = thread_key or self.thread_key
        if use_thread_key:
            payload["thread"] = {"threadKey": use_thread_key}
        
        #send message to google chat
        logger.info(f"Sending message to Google Chat from notifer client: {payload}")
        try:    
            http_obj = Http()
            
            response = http_obj.request(
                method="POST", 
                uri=self.webhook_url, 
                body=dumps(payload), 
                headers=message_headers,
            )
            return response
        except Exception as e:
            logger.error(f"Error sending message to Google Chat from notifer client: {e}")
            raise e