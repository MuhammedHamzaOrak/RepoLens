from dataclasses import dataclass
from typing import Literal

from app.providers.chat import ChatMessage, ChatProvider
from app.services.retrieval_service import RetrievedChunk, RetrievalService


@dataclass(frozen=True, slots=True)
class RagResult:
    answer: str
    answer_status: Literal["grounded", "insufficient_context"]
    sources: list[RetrievedChunk]


class RagService:
    def __init__(
        self,
        retrieval_service: RetrievalService,
        chat_provider: ChatProvider,
        system_prompt: str,
        max_context_chars: int,
    ) -> None:
        self.retrieval_service = retrieval_service
        self.chat_provider = chat_provider
        self.system_prompt = system_prompt.strip()
        self.max_context_chars = max_context_chars

    def answer(
        self,
        project_id: str,
        question: str,
        top_k: int | None = None,
    ) -> RagResult:
        retrieval = self.retrieval_service.search(
            project_id=project_id,
            query=question,
            top_k=top_k,
        )
        if retrieval.status == "insufficient_context" or not retrieval.results:
            return RagResult(
                answer=(
                    "Bu soruyu yanıtlamak için indekslenen proje kaynaklarında "
                    "yeterli bağlam bulunamadı."
                ),
                answer_status="insufficient_context",
                sources=[],
            )

        context, included_sources = self._build_context(retrieval.results)
        messages: list[ChatMessage] = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": (
                    "KULLANICI SORUSU:\n"
                    f"{question}\n\n"
                    "GÜVENİLMEYEN DEPO BAĞLAMI:\n"
                    f"{context}"
                ),
            },
        ]
        answer = self.chat_provider.complete(messages)
        return RagResult(
            answer=answer,
            answer_status="grounded",
            sources=included_sources,
        )

    def _build_context(
        self,
        results: list[RetrievedChunk],
    ) -> tuple[str, list[RetrievedChunk]]:
        blocks: list[str] = []
        included: list[RetrievedChunk] = []
        remaining = self.max_context_chars

        for index, item in enumerate(results, start=1):
            separator = "\n\n" if blocks else ""
            chunk = item.chunk
            header = (
                f"[SOURCE {index}]\n"
                f"File: {chunk['file_path']}\n"
                f"Symbol: {chunk['symbol_name'] or '(none)'}\n"
                f"Type: {chunk['symbol_type']}\n"
                f"Lines: {chunk['start_line']}-{chunk['end_line']}\n"
                "Content:\n"
            )
            block_budget = remaining - len(separator)
            if len(header) >= block_budget:
                break

            content = str(chunk["content"])
            available_content = block_budget - len(header)
            block = header + content[:available_content]
            blocks.append(block)
            included.append(item)
            remaining -= len(separator) + len(block)
            if len(content) > available_content or remaining <= 0:
                break

        return "\n\n".join(blocks), included
