"""GitHub webhook handler."""
from __future__ import annotations
import hmac
import hashlib
import logging
from fastapi import APIRouter, Header, HTTPException, Request
from prometheus_client import Counter, Histogram
from apps.shared.config import settings
from apps.shared.utils.github_events import GitHubEventNormalizer
from apps.shared.mq import get_mq_client

logger = logging.getLogger("app.webhooks.github")

# Prometheus metrics
webhook_received = Counter(
    "webhook_received_total",
    "Total webhooks received",
    ["event_type", "status"],
)
webhook_processing_time = Histogram(
    "webhook_processing_seconds",
    "Time spent processing webhook",
    ["event_type"],
)

router = APIRouter(prefix="/webhooks/github", tags=["webhooks:github"])


@router.post("")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None, alias="X-Hub-Signature-256"),
    x_github_event: str | None = Header(default=None, alias="X-GitHub-Event"),
    x_github_delivery: str | None = Header(default=None, alias="X-GitHub-Delivery"),
    user_agent: str | None = Header(default=None, alias="User-Agent"),
):
    """Handle GitHub webhook events."""
    with webhook_processing_time.labels(event_type=x_github_event or "unknown").time():
        # Basic UA guard (defense in depth)
        ua_prefix = settings.github_trusted_ua_prefix
        if ua_prefix and (not user_agent or not user_agent.startswith(ua_prefix)):
            webhook_received.labels(
                event_type=x_github_event or "unknown", status="invalid_ua"
            ).inc()
            raise HTTPException(status_code=400, detail="invalid user-agent")

        # Read raw body for HMAC verification
        body = await request.body()

        secret = settings.github_webhook_secret
        if not secret:
            webhook_received.labels(
                event_type=x_github_event or "unknown", status="config_error"
            ).inc()
            raise HTTPException(status_code=500, detail="webhook secret not configured")

        # Verify signature (X-Hub-Signature-256)
        if not x_hub_signature_256 or not x_hub_signature_256.startswith("sha256="):
            webhook_received.labels(
                event_type=x_github_event or "unknown", status="missing_signature"
            ).inc()
            raise HTTPException(status_code=400, detail="missing signature")

        digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        expected = f"sha256={digest}"
        if not hmac.compare_digest(expected, x_hub_signature_256):
            webhook_received.labels(
                event_type=x_github_event or "unknown", status="signature_mismatch"
            ).inc()
            raise HTTPException(status_code=401, detail="signature mismatch")

        # Parse JSON safely (don't crash on ping)
        try:
            payload = await request.json()
        except Exception as e:
            logger.warning(f"Failed to parse JSON payload: {e}")
            payload = {}

        # Log event
        logger.info(
            "GitHub delivery event=%s id=%s size=%s",
            x_github_event,
            x_github_delivery,
            len(body),
        )

        # Special-case ping for quick health checks
        if x_github_event == "ping":
            zen = payload.get("zen") if isinstance(payload, dict) else None
            webhook_received.labels(event_type="ping", status="success").inc()
            return {
                "ok": True,
                "pong": True,
                "zen": zen,
                "delivery": x_github_delivery,
            }

        # Normalize and enqueue event
        try:
            normalized = GitHubEventNormalizer.normalize_event(
                x_github_event or "", payload
            )
            
            if normalized:
                # Enqueue to message queue
                mq_client = get_mq_client()
                topic = f"github.{x_github_event}"
                await mq_client.publish(topic, normalized)
                
                logger.info(
                    "Enqueued event type=%s delivery=%s",
                    x_github_event,
                    x_github_delivery,
                )
                webhook_received.labels(
                    event_type=x_github_event or "unknown", status="success"
                ).inc()
            else:
                logger.warning(
                    "Unknown or unsupported event type: %s", x_github_event
                )
                webhook_received.labels(
                    event_type=x_github_event or "unknown", status="unsupported"
                ).inc()
        
        except Exception as e:
            logger.exception("Failed to process webhook event")
            webhook_received.labels(
                event_type=x_github_event or "unknown", status="error"
            ).inc()
            # Don't fail the webhook, just log
            return {
                "ok": False,
                "error": str(e),
                "event": x_github_event,
                "delivery": x_github_delivery,
            }

        return {
            "ok": True,
            "event": x_github_event,
            "delivery": x_github_delivery,
        }
