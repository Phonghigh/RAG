import json
import logging
from fastapi import FastAPI, HTTPException
from apps.shared.config import settings
from apps.notifer.client import GooogleChatNotifier

logger = logging.getLogger("app")
app = FastAPI(
    title=settings.app_name, 
    docs_url="/docs" if settings.app_env == "development" else None,
    redoc_url="/redoc" if settings.app_env == "development" else None,
    openapi_url="/openapi.json" if settings.app_env == "development" else None
)

# #health check endpoint
# @app.get("/health")
# async def health_check():
#     return {
#         "status": "ok",
#         "environment": settings.app_env
#     }

#root endpoint
@app.get("/")
def root():
    return {
        "status": "ok",
        "environment": settings.app_env
    }

#ping google chat endpoint
@app.post("/ping/google-chat")
def ping_google_chat():
    logger.info(f"Pinging Google Chat: {settings.google_chat_webhook_url}")
    #send message to google chat
    notifier = GooogleChatNotifier(
        webhook_url=settings.google_chat_webhook_url,
        thread_key=settings.google_chat_thread_key,
        notified_users=settings.google_chat_notified_users,
    )

    #build message
    message = f"Hello, world! This is a test message from the RCA-RAG API."
    logger.info(f"Sending message to Google Chat: {message}")
    try:

        response = notifier.send_message(text=message)
        logger.info(f"Response from Google Chat: {response}")
        return {
            "status": "ok",
            "message": response
        }
    except Exception as e:
        logger.error(f"Error sending message to Google Chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))

#run the app
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.app_host, port=settings.app_port)