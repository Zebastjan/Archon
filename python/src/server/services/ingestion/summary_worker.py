"""
Summary Worker

Processes summaries from the queue.
This is a separate pass that can be run independently of the download/chunk/embed flow.
"""

import uuid
from typing import Any

from ...config.logfire_config import get_logger, safe_logfire_error, safe_logfire_info
from ..llm_provider_service import extract_message_text, get_llm_client
from .ingestion_state_service import (
    SummaryStatus,
    SummaryStyle,
    get_ingestion_state_service,
)

logger = get_logger(__name__)

SUMMARY_PROMPTS = {
    SummaryStyle.OVERVIEW: """<source_content>
{content}
</source_content>

The above content is from the documentation for '{source_id}'. Please provide a concise summary (3-5 sentences) that describes what this library/tool/framework is about. The summary should help understand what the library/tool/framework accomplishes and the purpose.""",
    SummaryStyle.TECHNICAL: """<source_content>
{content}
</source_content>

Provide a technical summary of the above documentation. Focus on:
- API signatures and parameters
- Data structures and types
- Key functions and their purposes
- Configuration options

Be concise but technically accurate.""",
    SummaryStyle.USER: """<source_content>
{content}
</source_content>

Provide a user-friendly summary of the above documentation. Focus on:
- What problems this tool solves
- Basic getting started steps
- Common use cases
- Key benefits

Write for someone who is new to the tool.""",
    SummaryStyle.BRIEF: """<source_content>
{content}
</source_content>

Provide a very brief one-sentence summary of what this documentation is about.""",
}


class SummaryWorker:
    def __init__(self):
        self.state_service = get_ingestion_state_service()

    async def process_pending_summaries(
        self,
        summarizer_model_id: str | None = None,
        style: str | None = None,
        max_batch_size: int = 10,
    ) -> dict[str, Any]:
        pending = await self.state_service.get_pending_summaries(summarizer_model_id, style)

        if not pending:
            return {"processed": 0, "message": "No pending summaries"}

        results = {
            "processed": 0,
            "failed": 0,
            "summaries_processed": [],
        }

        for summary in pending[:max_batch_size]:
            try:
                success = await self._process_summary(summary)
                if success:
                    results["processed"] += 1
                    results["summaries_processed"].append(str(summary.id))
                else:
                    results["failed"] += 1
            except Exception as e:
                safe_logfire_error(f"Error processing summary {summary.id}: {e}")
                await self.state_service.update_summary(
                    summary.id,
                    SummaryStatus.FAILED,
                    error_info={"error": str(e), "stage": "summary_processing"},
                )
                results["failed"] += 1

        return results

    async def _process_summary(self, summary) -> bool:
        await self.state_service.update_summary(summary.id, SummaryStatus.IN_PROGRESS)

        blobs = await self.state_service.get_blobs_by_source(summary.source_id, status="downloaded")
        if not blobs:
            await self.state_service.update_summary(
                summary.id,
                SummaryStatus.FAILED,
                error_info={"error": "No downloaded blobs found for source"},
            )
            return False

        content_parts = []
        for blob in blobs:
            chunks = await self.state_service.get_chunks_by_blob(blob.id)
            content_parts.extend([c.content for c in chunks])

        combined_content = "\n\n".join(content_parts[:3])
        if len(combined_content) > 25000:
            combined_content = combined_content[:25000]

        try:
            summary_text = await self._generate_summary(
                summary.source_id,
                combined_content,
                summary.summarizer_model_id,
                summary.style,
            )

            await self.state_service.update_summary(
                summary.id,
                SummaryStatus.DONE,
                summary_content=summary_text,
            )

            await self._update_source_summary(summary.source_id, summary_text)

            safe_logfire_info(f"Summary {summary.id} completed for source {summary.source_id}")
            return True

        except Exception as e:
            safe_logfire_error(f"Failed to generate summary {summary.id}: {e}")
            await self.state_service.update_summary(
                summary.id,
                SummaryStatus.FAILED,
                error_info={"error": str(e), "stage": "summary_generation"},
            )
            return False

    async def _generate_summary(
        self,
        source_id: str,
        content: str,
        model_id: str,
        style: str,
    ) -> str:
        prompt_template = SUMMARY_PROMPTS.get(SummaryStyle(style), SUMMARY_PROMPTS[SummaryStyle.OVERVIEW])
        prompt = prompt_template.format(content=content, source_id=source_id)

        async with get_llm_client() as client:
            response = await client.chat.completions.create(
                model=model_id,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that provides concise library/tool/framework summaries.",
                    },
                    {"role": "user", "content": prompt},
                ],
            )

            if not response or not response.choices:
                raise Exception("Empty response from LLM")

            summary_text, _, _ = extract_message_text(response.choices[0])
            if not summary_text:
                raise Exception("LLM returned empty content")

            return summary_text.strip()

    async def _update_source_summary(self, source_id: str, summary: str) -> None:
        from ..database import get_database_connector
        db = get_database_connector()
        await db.execute(
            "UPDATE archon_sources SET summary = $1 WHERE source_id = $2",
            summary,
            source_id
        )

    async def retry_failed_summaries(
        self,
        summarizer_model_id: str | None = None,
        style: str | None = None,
    ) -> dict[str, Any]:
        from ..database import get_database_connector
        db = get_database_connector()

        if summarizer_model_id and style:
            result = await db.fetch(
                "SELECT * FROM archon_summaries WHERE status = $1 AND summarizer_model_id = $2 AND style = $3",
                "failed",
                summarizer_model_id,
                style
            )
        elif summarizer_model_id:
            result = await db.fetch(
                "SELECT * FROM archon_summaries WHERE status = $1 AND summarizer_model_id = $2",
                "failed",
                summarizer_model_id
            )
        elif style:
            result = await db.fetch(
                "SELECT * FROM archon_summaries WHERE status = $1 AND style = $2",
                "failed",
                style
            )
        else:
            result = await db.fetch(
                "SELECT * FROM archon_summaries WHERE status = $1",
                "failed"
            )

        updated = 0
        for row in result:
            await self.state_service.update_summary(uuid.UUID(row["id"]), SummaryStatus.PENDING)
            updated += 1

        return {"reset": updated}


def get_summary_worker() -> SummaryWorker:
    return SummaryWorker()
