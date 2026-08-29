"""POST /feedback — record a user's verdict on a report.

WHAT THIS IS: an append-only JSONL log. One line per submission.

WHAT THIS IS NOT: a learning loop. Nothing in the pipeline reads this file
back, no model is retrained, no threshold moves. The problem statement asks
for a mechanism to learn from analyst feedback and the honest state of that is
"we capture it, structured, from the first run" — which is the first hop of the
Living Knowledge Base on the roadmap, not the whole thing. Any UI copy or deck
claim beyond that is a claim we cannot defend, and a judge who asks "so what
happens to my feedback?" must get a straight answer.

Failure behaviour follows the same rule as the rest of C2: a disk problem
degrades into a structured `recorded: false` at HTTP 200, never a 500. Losing
one feedback line must never take down the screen the user is reading.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter

from api.config.settings import settings
from api.models.internal import FeedbackRequest, FeedbackResponse

router = APIRouter()
logger = logging.getLogger(__name__)


def _append_line(record: dict) -> None:
    """Blocking: create the parent directory if needed and append one JSON line."""
    path = Path(settings.FEEDBACK_LOG_PATH)
    if path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


@router.post("/feedback", response_model=FeedbackResponse)
async def feedback(request: FeedbackRequest) -> FeedbackResponse:
    record = request.model_dump(mode="json")
    # Server-side timestamp: the client's clock is not evidence. This is the
    # only field C2 adds, and it is measured, not supplied.
    record["received_at"] = datetime.now(timezone.utc).isoformat()

    try:
        # to_thread for the same reason C1/C3 get it: a slow or networked disk
        # must not block the event loop for every other request in flight.
        await asyncio.to_thread(_append_line, record)
    except OSError as exc:
        # Anticipated (read-only volume, full disk, bad configured path), so it
        # degrades rather than 500s.
        logger.warning(
            "feedback not recorded job_id=%s path=%s error=%s",
            request.job_id,
            settings.FEEDBACK_LOG_PATH,
            exc,
        )
        return FeedbackResponse(
            recorded=False,
            message="We couldn't save that just now — your report is unaffected.",
        )

    logger.info(
        "feedback recorded job_id=%s target=%s verdict=%s correction=%s",
        request.job_id,
        request.target,
        request.verdict.value,
        request.correction.value if request.correction else None,
    )
    return FeedbackResponse(recorded=True, message="Thanks — recorded.")
