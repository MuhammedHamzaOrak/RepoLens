from app.services.rag_service import RagService
from app.services.retrieval_service import RetrievedChunk


def _retrieved_chunk(chunk_id: str, content: str) -> RetrievedChunk:
    return RetrievedChunk(
        chunk={
            "id": chunk_id,
            "file_path": f"src/{chunk_id}.py",
            "symbol_name": f"function_{chunk_id}",
            "symbol_type": "function",
            "start_line": 1,
            "end_line": 10,
            "content": content,
        },
        score=0.9,
    )


def test_context_budget_keeps_multiple_ranked_sources_visible() -> None:
    service = RagService(
        retrieval_service=None,  # type: ignore[arg-type]
        chat_provider=None,  # type: ignore[arg-type]
        system_prompt="Grounded answers only.",
        max_context_chars=1000,
    )
    results = [
        _retrieved_chunk("large", "first source\n" * 1000),
        _retrieved_chunk("small", "important second source"),
    ]

    context, included_sources = service._build_context(results)

    assert len(context) <= 1000
    assert [item.chunk["id"] for item in included_sources] == ["large", "small"]
    assert "File: src/large.py" in context
    assert "File: src/small.py" in context
    assert "important second source" in context


def test_answer_prompt_requests_concrete_short_code_explanation() -> None:
    class StubRetrievalService:
        def search(self, **kwargs):
            return type(
                "Retrieval",
                (),
                {
                    "status": "ok",
                    "strategy": "implementation",
                    "results": [
                        _retrieved_chunk("adder", "return left + right"),
                        _retrieved_chunk("helper", "build the expression"),
                        _retrieved_chunk("search", "rank matching chunks"),
                        _retrieved_chunk("fourth", "must not reach the prompt"),
                    ],
                },
            )()

    class RecordingChatProvider:
        def __init__(self) -> None:
            self.messages = None

        def complete(self, messages):
            self.messages = messages
            return "Toplama + operatörüyle yapılır."

    provider = RecordingChatProvider()
    service = RagService(
        retrieval_service=StubRetrievalService(),  # type: ignore[arg-type]
        chat_provider=provider,  # type: ignore[arg-type]
        system_prompt="Grounded answers only.",
        max_context_chars=1000,
    )

    result = service.answer("project", "Toplama nasıl yapılıyor?")

    assert result.answer_status == "grounded"
    assert provider.messages is not None
    assert "Answer in Turkish" in provider.messages[1]["content"]
    assert "at most three short sentences" in provider.messages[1]["content"]
    assert "controlling inputs" in provider.messages[1]["content"]
    assert "include their names in backticks" in provider.messages[1]["content"]
    assert "return left + right" in provider.messages[1]["content"]
    assert "must not reach the prompt" not in provider.messages[1]["content"]
    assert [source.chunk["id"] for source in result.sources] == [
        "adder",
        "helper",
        "search",
    ]


def test_overview_strategy_requests_a_project_summary() -> None:
    class StubRetrievalService:
        def search(self, **kwargs):
            return type(
                "Retrieval",
                (),
                {
                    "status": "ok",
                    "strategy": "overview",
                    "results": [
                        _retrieved_chunk(
                            "readme",
                            "A calculator for integer arithmetic.",
                        )
                    ],
                },
            )()

    class RecordingChatProvider:
        def __init__(self) -> None:
            self.messages = None

        def complete(self, messages):
            self.messages = messages
            return (
                "Proje tam sayı işlemleri yapan bir hesap makinesidir. "
                "İki sayı üzerinde dört temel işlemi uygular. "
                "Bu üçüncü cümle özet yanıtına girmemelidir."
            )

    provider = RecordingChatProvider()
    service = RagService(
        retrieval_service=StubRetrievalService(),  # type: ignore[arg-type]
        chat_provider=provider,  # type: ignore[arg-type]
        system_prompt="Grounded answers only.",
        max_context_chars=1000,
    )

    result = service.answer("project", "Proje hangi konu ile alakalı?")

    assert result.answer_status == "grounded"
    assert result.answer == (
        "Proje tam sayı işlemleri yapan bir hesap makinesidir. "
        "İki sayı üzerinde dört temel işlemi uygular."
    )
    assert provider.messages is not None
    assert "exactly two short prose sentences" in provider.messages[1]["content"]
    assert "Do not use headings, bullet points" in provider.messages[1]["content"]


def test_answer_language_detects_turkish_and_defaults_to_english() -> None:
    service = RagService(
        retrieval_service=None,  # type: ignore[arg-type]
        chat_provider=None,  # type: ignore[arg-type]
        system_prompt="Grounded answers only.",
        max_context_chars=1000,
    )

    assert service._answer_language("Toplama nasıl yapılıyor?") == "Turkish"
    assert service._answer_language("Bu endpoint ne yapar?") == "Turkish"
    assert service._answer_language("How does addition work?") == "English"


def test_clean_answer_removes_duplicate_sentences_and_caps_output() -> None:
    service = RagService(
        retrieval_service=None,  # type: ignore[arg-type]
        chat_provider=None,  # type: ignore[arg-type]
        system_prompt="Grounded answers only.",
        max_context_chars=1000,
    )

    answer = service._clean_answer(
        "First. Second. Second. Third. Fourth. Fifth."
    )

    assert answer == "First. Second. Third. Fourth."


def test_clean_answer_removes_incomplete_numbered_list_tail() -> None:
    service = RagService(
        retrieval_service=None,  # type: ignore[arg-type]
        chat_provider=None,  # type: ignore[arg-type]
        system_prompt="Grounded answers only.",
        max_context_chars=1000,
    )

    answer = service._clean_answer(
        "Projenin amacı hesaplama yapmaktır. İki sayıyı işler. "
        "Kullanılan parçalar şunlardır:\n\n1."
    )

    assert answer == "Projenin amacı hesaplama yapmaktır. İki sayıyı işler."


def test_operation_prefix_is_added_only_when_grounded_in_context() -> None:
    service = RagService(
        retrieval_service=None,  # type: ignore[arg-type]
        chat_provider=None,  # type: ignore[arg-type]
        system_prompt="Grounded answers only.",
        max_context_chars=1000,
    )

    prefix = service._operation_prefix(
        "Toplama işlemini nasıl yapıyor?",
        "signs = ['+', '-']",
        "İfadeyi eval ile hesaplar.",
        "Turkish",
    )

    assert prefix == "Kod, toplama işlemi için `+` operatörünü kullanır."
    assert service._operation_prefix(
        "Adres nerede ekleniyor?",
        "signs = ['+']",
        "Adres kaydedilir.",
        "Turkish",
    ) is None
    assert service._operation_prefix(
        "Toplama işlemini nasıl yapıyor?",
        "return stored_total",
        "Toplamı döndürür.",
        "Turkish",
    ) is None


def test_follow_up_uses_bounded_history_for_retrieval_and_prompt() -> None:
    class RecordingRetrievalService:
        def __init__(self) -> None:
            self.search_kwargs = None

        def search(self, **kwargs):
            self.search_kwargs = kwargs
            return type(
                "Retrieval",
                (),
                {
                    "status": "ok",
                    "strategy": "implementation",
                    "results": [
                        _retrieved_chunk(
                            "calculator",
                            "sign = '+'\nexpression = f'{left}{sign}{right}'",
                        )
                    ],
                },
            )()

    class RecordingChatProvider:
        def __init__(self) -> None:
            self.messages = None

        def complete(self, messages):
            self.messages = messages
            return "İşlem, seçilen operatöre göre bir ifade oluşturur."

    retrieval = RecordingRetrievalService()
    provider = RecordingChatProvider()
    service = RagService(
        retrieval_service=retrieval,  # type: ignore[arg-type]
        chat_provider=provider,  # type: ignore[arg-type]
        system_prompt="Ground every claim in repository context.",
        max_context_chars=1000,
    )
    history = [
        {"role": "user", "content": "discarded user 1"},
        {"role": "assistant", "content": "discarded assistant 1"},
        {"role": "user", "content": "Bu proje ne işe yarıyor?"},
        {
            "role": "assistant",
            "content": "Dört temel işlem yapan bir hesap makinesidir.",
        },
        {"role": "user", "content": "Toplama ve çıkarma yapıyor mu?"},
        {"role": "assistant", "content": "Evet, bu işlemleri destekler."},
        {"role": "user", "content": "Nasıl seçiliyor?"},
        {"role": "assistant", "content": "Bir işaret seçilir."},
    ]

    result = service.answer(
        "project",
        "İşlemleri neye göre yapıyor?",
        history=history,  # type: ignore[arg-type]
    )

    assert result.answer_status == "grounded"
    assert retrieval.search_kwargs is not None
    contextual_query = retrieval.search_kwargs["contextual_query"]
    assert contextual_query.startswith("İşlemleri neye göre yapıyor?")
    assert "Bir işaret seçilir." in contextual_query
    assert "Dört temel işlem" not in contextual_query
    assert "discarded user 1" not in contextual_query
    assert provider.messages is not None
    prompt = provider.messages[1]["content"]
    assert "CURRENT QUESTION:\nHow does the code" in prompt
    assert "arithmetic operations shown in the source" in prompt
    assert "Answer in English" in prompt
    assert "Dört temel işlem" not in prompt
    assert "discarded assistant 1" not in prompt
    assert [source.chunk["id"] for source in result.sources] == ["calculator"]


def test_explicit_new_question_does_not_use_history_for_retrieval() -> None:
    class RecordingRetrievalService:
        def __init__(self) -> None:
            self.search_kwargs = None

        def search(self, **kwargs):
            self.search_kwargs = kwargs
            return type(
                "Retrieval",
                (),
                {
                    "status": "insufficient_context",
                    "strategy": "default",
                    "results": [],
                },
            )()

    retrieval = RecordingRetrievalService()
    service = RagService(
        retrieval_service=retrieval,  # type: ignore[arg-type]
        chat_provider=None,  # type: ignore[arg-type]
        system_prompt="Grounded answers only.",
        max_context_chars=1000,
    )

    result = service.answer(
        "project",
        "Generator dosyası ne işe yarıyor?",
        history=[
            {"role": "user", "content": "README ne anlatıyor?"},
            {"role": "assistant", "content": "Kurulum adımlarını anlatıyor."},
        ],  # type: ignore[arg-type]
    )

    assert result.answer_status == "insufficient_context"
    assert retrieval.search_kwargs is not None
    assert retrieval.search_kwargs["contextual_query"] is None


def test_rewritten_turkish_follow_up_translates_grounded_analysis() -> None:
    class StubRetrievalService:
        def search(self, **kwargs):
            return type(
                "Retrieval",
                (),
                {
                    "status": "ok",
                    "strategy": "implementation",
                    "results": [
                        _retrieved_chunk(
                            "calculator",
                            "signs = ['+', '-']\nequation = f'{left}{sign}{right}'",
                        )
                    ],
                },
            )()

    class TranslatingChatProvider:
        def __init__(self) -> None:
            self.calls = []

        def complete(self, messages):
            self.calls.append(messages)
            if len(self.calls) == 1:
                return (
                    "The `sign` input selects the operator. "
                    "The code evaluates the constructed expression."
                )
            return (
                "İşte çeviri Türkçe:\n\n`sign` girdisi operatörü seçer. "
                "Kod oluşturulan ifadeyi hesaplar."
            )

    provider = TranslatingChatProvider()
    service = RagService(
        retrieval_service=StubRetrievalService(),  # type: ignore[arg-type]
        chat_provider=provider,  # type: ignore[arg-type]
        system_prompt="Grounded answers only.",
        max_context_chars=1000,
    )

    result = service.answer(
        "project",
        "İşlemleri neye göre yapıyor?",
        history=[
            {"role": "assistant", "content": "Dört işlem desteklenir."}
        ],  # type: ignore[arg-type]
    )

    assert result.answer == (
        "`sign` girdisi operatörü seçer. Kod oluşturulan ifadeyi hesaplar."
    )
    assert len(provider.calls) == 2
    assert "Answer in English" in provider.calls[0][1]["content"]
    assert "precise technical translator" in provider.calls[1][0]["content"]
    assert "Preserve all facts" in provider.calls[1][0]["content"]
    assert [source.chunk["id"] for source in result.sources] == ["calculator"]
