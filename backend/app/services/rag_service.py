import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from app.providers.chat import ChatMessage, ChatProvider
from app.services.query_intent import (
    detect_operation,
    is_context_dependent_query,
    is_mechanism_query,
    tokenize_query,
)
from app.services.retrieval_service import RetrievedChunk, RetrievalService


TURKISH_CHARACTERS = set("çğıöşüÇĞİÖŞÜ")
TURKISH_WORDS = {
    "bu",
    "hangi",
    "ile",
    "mı",
    "mi",
    "mu",
    "mü",
    "nasıl",
    "ne",
    "nerede",
    "neden",
}
MAX_HISTORY_MESSAGES = 6
MAX_RETRIEVAL_HISTORY_CHARS = 1000


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
        implementation_context_chunks: int = 3,
    ) -> None:
        self.retrieval_service = retrieval_service
        self.chat_provider = chat_provider
        self.system_prompt = system_prompt.strip()
        self.max_context_chars = max_context_chars
        self.implementation_context_chunks = implementation_context_chunks

    def answer(
        self,
        project_id: str,
        question: str,
        top_k: int | None = None,
        history: Sequence[ChatMessage] | None = None,
    ) -> RagResult:
        recent_history = self._bounded_history(history)
        contextual_query = (
            self._build_contextual_query(question, recent_history)
            if recent_history and is_context_dependent_query(question)
            else None
        )
        retrieval = self.retrieval_service.search(
            project_id=project_id,
            query=question,
            top_k=top_k,
            contextual_query=contextual_query,
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

        context_results = (
            retrieval.results[: self.implementation_context_chunks]
            if retrieval.strategy == "implementation"
            else retrieval.results
        )
        context, included_sources = self._build_context(context_results)
        answer_language = self._answer_language(question)
        question_for_generation = self._question_for_generation(
            question,
            retrieval.strategy,
            is_follow_up=contextual_query is not None,
        )
        generation_language = (
            "English"
            if answer_language == "Turkish" and question_for_generation != question
            else answer_language
        )
        if retrieval.strategy == "overview":
            answer_instruction = (
                f"Answer in {generation_language} using exactly two short prose "
                "sentences. First state the project's purpose, then its main "
                "behavior. Do not use headings, bullet points, or numbered lists."
            )
        else:
            answer_instruction = (
                f"Answer in {generation_language} using at most three short "
                "sentences. Answer the CURRENT QUESTION directly and explain "
                "the concrete code behavior. When the question asks how, why, "
                "or what determines behavior, name the controlling inputs, "
                "conditions, variables, or data flow from the repository "
                "context instead of merely repeating the project's supported "
                "features or the prior conversation. Mention relevant "
                "operators, functions, or identifiers. Before answering, "
                "identify the exact controlling identifiers in the source and "
                "include their names in backticks in the final answer. If the "
                "question names an operation, state its exact matching "
                "operator first, then explain how the code constructs and "
                "evaluates the expression. Do not copy the repository context."
            )
        messages: list[ChatMessage] = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": (
                    "REPOSITORY CONTEXT:\n"
                    f"{context}\n\n"
                    "CURRENT QUESTION:\n"
                    f"{question_for_generation}\n\n"
                    f"{answer_instruction}"
                ),
            },
        ]
        answer_sentence_limit = 2 if retrieval.strategy == "overview" else 3
        answer = self._clean_answer(
            self.chat_provider.complete(messages),
            max_sentences=answer_sentence_limit,
        )
        if (
            generation_language != answer_language
            and self._answer_language(answer) != answer_language
        ):
            answer = self._clean_answer(
                self._translate_answer(answer, answer_language),
                max_sentences=answer_sentence_limit,
            )
        operation_prefix = self._operation_prefix(
            question,
            context,
            answer,
            answer_language,
        )
        if operation_prefix:
            answer = self._clean_answer(
                f"{operation_prefix} {answer}",
                max_sentences=3,
            )
        return RagResult(
            answer=answer,
            answer_status="grounded",
            sources=included_sources,
        )

    def _bounded_history(
        self,
        history: Sequence[ChatMessage] | None,
    ) -> list[ChatMessage]:
        if not history:
            return []
        return [
            {"role": item["role"], "content": item["content"].strip()}
            for item in history[-MAX_HISTORY_MESSAGES:]
            if item["role"] in {"user", "assistant"} and item["content"].strip()
        ]

    def _build_contextual_query(
        self,
        question: str,
        history: Sequence[ChatMessage],
    ) -> str:
        previous_assistant = next(
            (
                item["content"]
                for item in reversed(history)
                if item["role"] == "assistant"
            ),
            None,
        )
        previous_user = next(
            (
                item["content"]
                for item in reversed(history)
                if item["role"] == "user"
            ),
            None,
        )
        reference = previous_assistant or previous_user or ""
        reference = reference[-MAX_RETRIEVAL_HISTORY_CHARS:]
        return f"{question}\n{reference}".strip()

    def _answer_language(self, question: str) -> str:
        if any(character in question for character in TURKISH_CHARACTERS):
            return "Turkish"
        words = set(re.findall(r"\w+", question.casefold()))
        return "Turkish" if words & TURKISH_WORDS else "English"

    def _question_for_generation(
        self,
        question: str,
        strategy: str,
        *,
        is_follow_up: bool,
    ) -> str:
        if (
            not is_follow_up
            or strategy != "implementation"
            or not is_mechanism_query(question)
        ):
            return question

        tokens = tokenize_query(question)
        refers_to_operations = any(
            token.startswith(("islem", "operation")) for token in tokens
        )
        if refers_to_operations:
            resolved_question = (
                "How does the code choose among the "
                "arithmetic operations shown in the source and calculate the "
                "result? Identify the controlling user inputs, variables, "
                "operators, and conditions."
            )
        else:
            resolved_question = (
                "How does the code perform the behavior "
                "referenced by this follow-up? Identify the controlling inputs, "
                "variables, conditions, and data flow."
            )
        return resolved_question

    def _translate_answer(self, answer: str, target_language: str) -> str:
        translation_messages: list[ChatMessage] = [
            {
                "role": "system",
                "content": (
                    "You are a precise technical translator. Translate only "
                    f"the supplied answer into {target_language}. Preserve all "
                    "facts, code identifiers, backticks, operators, and quoted "
                    "values exactly. Do not add, remove, explain, or summarize."
                ),
            },
            {"role": "user", "content": answer},
        ]
        return self.chat_provider.complete(translation_messages)

    def _clean_answer(self, answer: str, max_sentences: int = 4) -> str:
        cleaned_answer = re.sub(
            r"^\s*(?:(?:işte\s+)?(?:türkçe\s+)?çeviri(?:si)?"
            r"(?:\s+türkçe)?|translation)\s*:\s*",
            "",
            answer.strip(),
            flags=re.IGNORECASE,
        )
        cleaned_answer = self._strip_incomplete_list_tail(cleaned_answer)
        sentences = re.split(r"(?<=[.!?])\s+", cleaned_answer)
        unique_sentences: list[str] = []
        seen: set[str] = set()
        for sentence in sentences:
            normalized = " ".join(sentence.split()).casefold()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            unique_sentences.append(sentence.strip())
            if len(unique_sentences) == max_sentences:
                break
        return " ".join(unique_sentences)

    def _strip_incomplete_list_tail(self, answer: str) -> str:
        list_start = re.search(r"\n\s*(?:[-*•]|\d+[.)])(?:\s|$)", answer)
        if list_start is None:
            return answer

        prose = answer[: list_start.start()].rstrip()
        if prose.endswith(":"):
            last_sentence_end = max(
                prose.rfind("."),
                prose.rfind("!"),
                prose.rfind("?"),
            )
            if last_sentence_end >= 0:
                prose = prose[: last_sentence_end + 1]
        return prose or answer

    def _operation_prefix(
        self,
        question: str,
        context: str,
        answer: str,
        answer_language: str,
    ) -> str | None:
        operation = detect_operation(question)
        if (
            operation is None
            or operation.operator not in context
            or f"`{operation.operator}`" in answer
        ):
            return None
        if answer_language == "Turkish":
            return (
                f"Kod, {operation.turkish_name} işlemi için "
                f"`{operation.operator}` operatörünü kullanır."
            )
        return (
            f"The code uses the `{operation.operator}` operator for "
            f"{operation.english_name}."
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
            remaining_sources = len(results) - index + 1
            chunk = item.chunk
            header = (
                f"[SOURCE {index}]\n"
                f"File: {chunk['file_path']}\n"
                f"Symbol: {chunk['symbol_name'] or '(none)'}\n"
                f"Type: {chunk['symbol_type']}\n"
                f"Lines: {chunk['start_line']}-{chunk['end_line']}\n"
                "Content:\n"
            )
            block_budget = (remaining // remaining_sources) - len(separator)
            if len(header) >= block_budget:
                break

            content = str(chunk["content"])
            available_content = block_budget - len(header)
            block = header + content[:available_content]
            blocks.append(block)
            included.append(item)
            remaining -= len(separator) + len(block)
            if remaining <= 0:
                break

        return "\n\n".join(blocks), included
