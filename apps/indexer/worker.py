"""RAG indexer worker."""
import asyncio
import logging
from typing import List, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from apps.shared.db import get_async_session
from apps.shared.db.models import Diff, Repo
from apps.shared.mq import get_mq_client, MQClient
from apps.shared.storage import get_storage_client
from apps.analysis.parsers import get_parser
from apps.indexer.chunkers import FunctionChunker, FileChunker, PRChunker
from apps.indexer.embedder import Embedder
from apps.indexer.vector_store import VectorStore
from apps.shared.config import settings

logger = logging.getLogger("app.indexer.worker")


class IndexerWorker:
    """RAG indexing worker."""
    
    def __init__(self, enable_mq: bool = False):
        """
        Initialize indexer worker.
        
        Args:
            enable_mq: If True, enable message queue mode for automatic indexing
        """
        self.storage = get_storage_client()
        self.embedder = Embedder(
            model_name=getattr(settings, 'embedding_model_name', 'all-MiniLM-L6-v2')
        )
        self.function_chunker = FunctionChunker()
        self.file_chunker = FileChunker()
        self.pr_chunker = PRChunker()
        self.enable_mq = enable_mq
        self.mq_client: Optional[MQClient] = None
        self.running = False
        
        if enable_mq:
            self.mq_client = get_mq_client()
    
    async def index_diff(self, diff: Diff, session: AsyncSession) -> int:
        """
        Index a single diff.
        
        Args:
            diff: Diff model instance
            session: Database session
            
        Returns:
            Number of chunks indexed
        """
        if not diff.object_uri:
            logger.warning(f"Diff {diff.id} has no object_uri")
            return 0
        
        # Fetch diff content from storage
        # Parse object_uri (format: http://endpoint/bucket/key or s3://bucket/key)
        try:
            if not diff.object_uri:
                return 0
            
            # Parse URI
            from urllib.parse import urlparse
            object_uri = diff.object_uri
            parsed_uri = urlparse(object_uri)
            
            bucket = None
            key = None
            
            if parsed_uri.scheme == 's3':
                # s3://bucket/key format
                bucket = parsed_uri.netloc
                key = parsed_uri.path.lstrip('/')
            elif parsed_uri.scheme in ('http', 'https'):
                # http://endpoint/bucket/key format
                path_parts = parsed_uri.path.strip('/').split('/', 1)
                if len(path_parts) == 2:
                    bucket, key = path_parts
                else:
                    logger.warning(f"Invalid object_uri format: {object_uri}")
                    return 0
            else:
                logger.warning(f"Unknown URI scheme in object_uri: {object_uri}")
                return 0
            
            if not bucket or not key:
                logger.warning(f"Could not extract bucket/key from object_uri: {object_uri}")
                return 0
            
            diff_content_bytes = await self.storage.download_file(bucket, key)
            diff_content = diff_content_bytes.decode('utf-8')
        except Exception as e:
            logger.exception(f"Error fetching diff content: {e}")
            return 0
        
        if not diff_content:
            return 0
        
        # Parse file if possible
        parser = get_parser(diff.path or '', diff.lang)
        parsed_file = None
        
        if parser:
            try:
                parsed_file = parser.parse_file(diff_content, diff.path or '')
            except Exception as e:
                logger.warning(f"Error parsing file {diff.path}: {e}")
        
        # Generate chunks
        chunks = []
        
        if parsed_file and parsed_file.functions:
            # Function-level chunking
            func_chunks = self.function_chunker.chunk(parsed_file, diff_content)
            chunks.extend(func_chunks)
        
        if parsed_file:
            # File-level chunking (for small files)
            file_chunks = self.file_chunker.chunk(parsed_file, diff_content)
            chunks.extend(file_chunks)
        
        if not chunks:
            # Fallback: PR diff chunking
            pr_chunks = self.pr_chunker.chunk(diff_content, diff.path or '', {
                'diff_id': diff.id,
                'pr_id': diff.pr_id,
            })
            chunks.extend(pr_chunks)
        
        if not chunks:
            logger.warning(f"No chunks generated for diff {diff.id}")
            return 0
        
        # Generate embeddings
        chunk_texts = [chunk['content'] for chunk in chunks]
        try:
            embeddings = self.embedder.embed(chunk_texts)
        except Exception as e:
            logger.exception(f"Error generating embeddings: {e}")
            return 0
        
        # Add embeddings to chunks
        for chunk, embedding in zip(chunks, embeddings):
            chunk['embedding'] = embedding
        
        # Store in vector database
        vector_store = VectorStore(session)
        source_id = str(diff.id) if diff.id else None
        
        upserted = await vector_store.upsert_chunks(
            repo_id=diff.repo_id,
            chunks=chunks,
            source_type='diff',
            source_id=source_id,
            commit_sha=diff.commit.sha if diff.commit else None,
            path=diff.path,
            lang=diff.lang,
        )
        
        return upserted
    
    async def index_repo_diffs(self, repo_id: int, session: AsyncSession) -> int:
        """
        Index all diffs for a repository.
        
        Args:
            repo_id: Repository ID
            session: Database session
            
        Returns:
            Total chunks indexed
        """
        from sqlalchemy import select
        
        diffs = await session.scalars(
            select(Diff).where(Diff.repo_id == repo_id)
        )
        
        total_chunks = 0
        for diff in diffs:
            try:
                chunks = await self.index_diff(diff, session)
                total_chunks += chunks
            except Exception as e:
                logger.exception(f"Error indexing diff {diff.id}: {e}")
        
        await session.commit()
        logger.info(f"Indexed {total_chunks} chunks for repo_id={repo_id}")
        
        return total_chunks
    
    async def index_diffs_by_ids(
        self,
        diff_ids: List[int],
        session: AsyncSession
    ) -> int:
        """
        Index specific diffs by their IDs.
        
        Args:
            diff_ids: List of diff IDs to index
            session: Database session
            
        Returns:
            Total chunks indexed
        """
        if not diff_ids:
            return 0
        
        diffs = await session.scalars(
            select(Diff).where(Diff.id.in_(diff_ids))
        )
        
        total_chunks = 0
        for diff in diffs:
            try:
                chunks = await self.index_diff(diff, session)
                total_chunks += chunks
            except Exception as e:
                logger.exception(f"Error indexing diff {diff.id}: {e}")
        
        await session.commit()
        logger.info(f"Indexed {total_chunks} chunks for {len(diff_ids)} diffs")
        
        return total_chunks
    
    async def start(self):
        """Start the indexer worker in message queue mode."""
        if not self.enable_mq or not self.mq_client:
            raise RuntimeError("Message queue mode not enabled")
        
        logger.info("Starting indexer worker in message queue mode...")
        self.running = True
        
        # Subscribe to indexing requests
        await self.mq_client.subscribe(
            "indexing.requested",
            self._handle_indexing_message,
            group_id="indexer-worker",
        )
        
        logger.info("Indexer worker started, subscribed to topic: indexing.requested")
        
        # Keep running
        try:
            while self.running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        finally:
            await self.stop()
    
    async def stop(self):
        """Stop the indexer worker."""
        logger.info("Stopping indexer worker...")
        self.running = False
        if self.mq_client:
            await self.mq_client.close()
        logger.info("Indexer worker stopped")
    
    async def _handle_indexing_message(self, message: dict):
        """Handle indexing request message."""
        event_type = message.get("event_type")
        
        if event_type != "indexing.requested":
            logger.warning(f"Unknown event type: {event_type}")
            return
        
        repo_id = message.get("repo_id")
        pr_id = message.get("pr_id")
        pr_number = message.get("pr_number")
        diff_ids = message.get("diff_ids", [])
        
        if not diff_ids:
            logger.warning(f"No diff_ids in indexing request for PR {pr_id}")
            return
        
        logger.info(
            f"Processing indexing request for PR {pr_number} "
            f"(repo_id={repo_id}, pr_id={pr_id}, diffs={len(diff_ids)})"
        )
        
        async for session in get_async_session():
            try:
                total_chunks = await self.index_diffs_by_ids(diff_ids, session)
                logger.info(
                    f"Indexing complete for PR {pr_number}: "
                    f"{total_chunks} chunks indexed from {len(diff_ids)} diffs"
                )
            except Exception as e:
                logger.exception(f"Error processing indexing request: {e}")
                await session.rollback()
            finally:
                await session.close()


async def main():
    """Main entry point for manual indexing or message queue mode."""
    import sys
    
    # Check if running in MQ mode (--mq flag)
    if "--mq" in sys.argv or "-m" in sys.argv:
        # Run in message queue mode
        worker = IndexerWorker(enable_mq=True)
        await worker.start()
    elif len(sys.argv) > 1:
        # Manual mode: index specific repo
        repo_id = int(sys.argv[1])
        
        async for session in get_async_session():
            try:
                worker = IndexerWorker()
                total = await worker.index_repo_diffs(repo_id, session)
                print(f"Indexed {total} chunks")
            finally:
                await session.close()
    else:
        print("Usage:")
        print("  python -m apps.indexer <repo_id>  # Manual indexing")
        print("  python -m apps.indexer --mq       # Message queue mode")


if __name__ == "__main__":
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    asyncio.run(main())
