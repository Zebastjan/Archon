"""Document summarization service.

Generates summaries at document and section level using LLM.
Stores summaries alongside embeddings for retrieval.
"""

from dataclasses import dataclass, field
from typing import Any

from ...config.logfire_config import get_logger
from ..llm_provider_service import get_llm_client, extract_message_text

logger = get_logger(__name__)


@dataclass
class DocumentSummary:
    """Summary of a document or section.

    Attributes:
        text: The summary text
        level: Summary level (document/section)
        heading: Section heading (if section-level)
        word_count: Original word count
        keywords: Extracted keywords
    """

    text: str
    level: str = "document"  # "document" or "section"
    heading: str = ""
    word_count: int = 0
    keywords: list[str] = field(default_factory=list)


class SummarizationService:
    """Service for document summarization.

    Generates summaries using LLM and stores them for retrieval.
    """

    # Default prompt templates
    DOCUMENT_SUMMARY_PROMPT = """Provide a concise summary (2-3 sentences) of the following document.
Focus on the main purpose and key points. Be factual and objective.

Document:
{text}

Summary:"""

    SECTION_SUMMARY_PROMPT = """Summarize this section in 1-2 sentences.
Focus on the key information and main takeaway.

Section: {heading}

Content:
{text}

Summary:"""

    def __init__(self, provider: str | None = None):
        """Initialize summarization service.

        Args:
            provider: Optional LLM provider override
        """
        self.provider = provider

    async def summarize_document(
        self,
        content: str,
        title: str = "",
        max_length: int = 300,
    ) -> DocumentSummary:
        """Generate document-level summary.

        Args:
            content: Full document content
            title: Document title
            max_length: Maximum summary length

        Returns:
            Document summary
        """
        word_count = len(content.split())

        # For very long documents, sample content
        if word_count > 2000:
            content = self._sample_content(content, max_words=1500)

        prompt = self.DOCUMENT_SUMMARY_PROMPT.format(text=content)

        try:
            summary_text = await self._generate_summary(prompt, max_length)

            # Extract keywords
            keywords = await self._extract_keywords(content)

            return DocumentSummary(
                text=summary_text,
                level="document",
                word_count=word_count,
                keywords=keywords,
            )

        except Exception as e:
            logger.error(f"Document summarization failed: {e}")
            return DocumentSummary(
                text=f"Document about {title or 'unknown topic'}. Full text available for retrieval.",
                level="document",
                word_count=word_count,
            )

    async def summarize_section(
        self,
        content: str,
        heading: str,
        max_length: int = 150,
    ) -> DocumentSummary:
        """Generate section-level summary.

        Args:
            content: Section content
            heading: Section heading
            max_length: Maximum summary length

        Returns:
            Section summary
        """
        word_count = len(content.split())

        prompt = self.SECTION_SUMMARY_PROMPT.format(
            heading=heading,
            text=content[:2000],  # Limit context
        )

        try:
            summary_text = await self._generate_summary(prompt, max_length)

            return DocumentSummary(
                text=summary_text,
                level="section",
                heading=heading,
                word_count=word_count,
            )

        except Exception as e:
            logger.error(f"Section summarization failed: {e}")
            return DocumentSummary(
                text=f"Section: {heading}. Content available.",
                level="section",
                heading=heading,
                word_count=word_count,
            )

    async def summarize_sections(
        self,
        sections: list[dict[str, Any]],
    ) -> list[DocumentSummary]:
        """Summarize multiple sections.

        Args:
            sections: List of section dicts with content and heading

        Returns:
            List of section summaries
        """
        import asyncio

        tasks = [
            self.summarize_section(
                section.get("content", ""),
                section.get("heading", ""),
            )
            for section in sections
        ]

        return await asyncio.gather(*tasks)

    async def _generate_summary(
        self,
        prompt: str,
        max_length: int,
    ) -> str:
        """Generate summary using LLM.

        Args:
            prompt: Summary prompt
            max_length: Maximum length

        Returns:
            Generated summary
        """
        async with get_llm_client(provider=self.provider) as client:
            response = await client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=max_length,
            )

            text = extract_message_text(response)
            return text.strip()[:max_length]

    async def _extract_keywords(self, content: str) -> list[str]:
        """Extract keywords from content.

        Args:
            content: Document content

        Returns:
            List of keywords
        """
        # Simple keyword extraction - could be enhanced with NLP
        import re

        # Extract words that appear multiple times
        words = re.findall(r"\b[A-Za-z]{4,}\b", content.lower())
        word_freq = {}

        for word in words:
            if word not in word_freq:
                word_freq[word] = 0
            word_freq[word] += 1

        # Return top keywords by frequency
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [word for word, freq in sorted_words[:10] if freq > 1]

    def _sample_content(self, content: str, max_words: int = 1500) -> str:
        """Sample content from long documents.

        Takes beginning, middle, and end sections for coverage.

        Args:
            content: Full content
            max_words: Maximum words to sample

        Returns:
            Sampled content
        """
        words = content.split()
        total = len(words)

        if total <= max_words:
            return content

        # Sample: 40% from beginning, 30% from middle, 30% from end
        beginning = words[: int(max_words * 0.4)]
        middle_start = (total - int(max_words * 0.3)) // 2
        middle = words[middle_start : middle_start + int(max_words * 0.3)]
        end = words[-int(max_words * 0.3) :]

        return " ".join(beginning + ["[...]"] + middle + ["[...]"] + end)


# Convenience functions
async def summarize_document(
    content: str,
    title: str = "",
    provider: str | None = None,
) -> DocumentSummary:
    """Summarize a document.

    Args:
        content: Document content
        title: Document title
        provider: Optional LLM provider

    Returns:
        Document summary
    """
    service = SummarizationService(provider=provider)
    return await service.summarize_document(content, title)


async def summarize_sections(
    sections: list[dict[str, Any]],
    provider: str | None = None,
) -> list[DocumentSummary]:
    """Summarize document sections.

    Args:
        sections: List of sections
        provider: Optional LLM provider

    Returns:
        List of summaries
    """
    service = SummarizationService(provider=provider)
    return await service.summarize_sections(sections)
