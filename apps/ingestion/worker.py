"""Ingestion worker main loop."""
import asyncio
import logging
import json
from typing import Callable
from sqlalchemy.ext.asyncio import AsyncSession
from apps.shared.db import get_async_session
from apps.shared.mq import get_mq_client, MQClient
from apps.ingestion.processors.github_events import GitHubEventProcessor
from apps.shared.config import settings

logger = logging.getLogger("app.ingestion.worker")


class IngestionWorker:
    """Main ingestion worker."""
    
    def __init__(self):
        """Initialize worker."""
        self.mq_client: MQClient = get_mq_client()
        self.running = False
    
    async def start(self):
        """Start the worker."""
        logger.info("Starting ingestion worker...")
        self.running = True
        
        # Subscribe to GitHub events
        topics = [
            "github.push",
            "github.pull_request",
            "github.pull_request_review",
            "github.check_run",
        ]
        
        for topic in topics:
            await self.mq_client.subscribe(
                topic,
                self._handle_message,
                group_id="ingestion-worker",
            )
        
        logger.info("Ingestion worker started, subscribed to topics: %s", topics)
        
        # Keep running
        try:
            while self.running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        finally:
            await self.stop()
    
    async def stop(self):
        """Stop the worker."""
        logger.info("Stopping ingestion worker...")
        self.running = False
        await self.mq_client.close()
        logger.info("Ingestion worker stopped")
    
    async def _handle_message(self, message: dict):
        """Handle a message from the queue."""
        event_type = message.get("event_type")
        logger.info(f"Processing event type={event_type}")
        
        async for session in get_async_session():
            try:
                processor = GitHubEventProcessor(session)
                
                if event_type == "push":
                    await processor.process_push_event(message)
                elif event_type == "pull_request":
                    await processor.process_pull_request_event(message)
                elif event_type == "check_run":
                    await processor.process_check_run_event(message)
                else:
                    logger.warning(f"Unknown event type: {event_type}")
                
            except Exception as e:
                logger.exception(f"Error processing event: {e}")
                # Rollback on error
                await session.rollback()
            finally:
                await session.close()


async def main():
    """Main entry point."""
    worker = IngestionWorker()
    await worker.start()


if __name__ == "__main__":
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    asyncio.run(main())

