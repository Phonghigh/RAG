"""Entry point for analysis worker."""
import asyncio
import logging
from apps.analysis.worker import main
from apps.shared.config import settings

if __name__ == "__main__":
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    asyncio.run(main())
