import pytest

from app.services.query_intent import (
    detect_operation,
    is_context_dependent_query,
    is_implementation_query,
    is_mechanism_query,
    is_project_overview_query,
    normalize_query,
)


@pytest.mark.parametrize(
    ("query", "english_name", "operator"),
    [
        ("Toplama işlemi nasıl yapılıyor?", "addition", "+"),
        ("Çıkarma işlemi nasıl yapılıyor?", "subtraction", "-"),
        ("Çarpma işlemi nasıl yapılıyor?", "multiplication", "*"),
        ("Bölme işlemi nasıl yapılıyor?", "division", "/"),
    ],
)
def test_detect_operation_handles_turkish_queries(
    query: str,
    english_name: str,
    operator: str,
) -> None:
    operation = detect_operation(query)

    assert operation is not None
    assert operation.english_name == english_name
    assert operation.operator == operator


def test_detect_operation_uses_whole_words() -> None:
    assert detect_operation("Where is the address formatter implemented?") is None


def test_detect_operation_does_not_treat_adding_a_record_as_arithmetic() -> None:
    assert detect_operation("Where does the code add a user?") is None
    assert detect_operation("How does the code add two numbers?") is not None


@pytest.mark.parametrize(
    "query",
    [
        "Proje ne üzerine kurulu?",
        "Proje hangi konu ile alakalı?",
        "Bu proje ne işe yarıyor?",
        "Ne işe yarıyor bu proje?",
        "Bu projenin amacı nedir?",
        "Hangi konu ile alakalı bu proje?",
        "Proje hakkında kısaca bilgi verir misin?",
        "Projeyi özetler misin?",
        "Bu nasıl bir proje?",
        "Bu ne projesi?",
        "Ne yapıyor bu proje?",
        "Neye yarar bu repo?",
        "Bu proje hangi problemi çözüyor?",
        "Ne ise yariyor bu porje?",
        "Ne ise yario bu poje?",
        "Bu kodun genel görevi nedir?",
        "What is this project about?",
        "What's this repository for?",
        "This repository does what?",
        "Give me an overview of the repo.",
        "Explain this application.",
        "How does this project work?",
    ],
)
def test_detect_project_overview_queries(query: str) -> None:
    assert is_project_overview_query(query)


@pytest.mark.parametrize(
    "query",
    [
        "Projedeki upload servisi ne işe yarıyor?",
        "Bu projenin README dosyası ne yapıyor?",
        "README dosyası bu projede ne işe yarar?",
        "Projedeki parserı açıkla.",
        "Projede hangi endpoint kullanıcı oluşturuyor?",
        "Kullanıcı projeye nasıl ekleniyor?",
        "Proje neden yavaş?",
        "Proje ne zaman oluşturuldu?",
        "Bu program ne zaman başlıyor?",
        "Bu prosedür ne işe yarıyor?",
        "Bu proje hangi Python sürümünü kullanıyor?",
        "What does the upload service do in this project?",
        "What is the purpose of the upload service in this project?",
    ],
)
def test_component_or_specific_questions_are_not_project_overviews(
    query: str,
) -> None:
    assert not is_project_overview_query(query)


@pytest.mark.parametrize(
    "query",
    [
        "Projedeki upload servisi ne işe yarıyor?",
        "Bu endpoint ne yapar?",
        "Kullanıcı kaydı hangi fonksiyonda?",
        "Toplama işlemi nasl yapiliyor?",
        "İşlemleri neye göre yapıyor?",
        "What does the upload service do in this project?",
    ],
)
def test_detect_implementation_queries_with_reordered_or_imperfect_text(
    query: str,
) -> None:
    assert is_implementation_query(query)


def test_query_normalization_handles_turkish_ascii_and_punctuation() -> None:
    assert normalize_query("  NE İŞE yarıyor, BU proje?! ") == (
        "ne ise yariyor bu proje"
    )


@pytest.mark.parametrize(
    "query",
    [
        "İşlemleri neye göre yapıyor?",
        "Peki bunu hangi fonksiyon yapıyor?",
        "Bunlar hangi dosyada?",
        "How does it work?",
        "Where is that function?",
    ],
)
def test_detect_context_dependent_follow_up_queries(query: str) -> None:
    assert is_context_dependent_query(query)


@pytest.mark.parametrize(
    "query",
    [
        "Bu proje ne işe yarıyor?",
        "Toplama işlemi nasıl yapılıyor?",
        "Generator dosyası ne işe yarıyor?",
        "Where is user registration implemented?",
    ],
)
def test_explicit_questions_do_not_require_conversation_context(query: str) -> None:
    assert not is_context_dependent_query(query)


@pytest.mark.parametrize(
    "query",
    [
        "İşlemleri neye göre yapıyor?",
        "Bu nasıl çalışıyor?",
        "Why does it behave this way?",
    ],
)
def test_detect_mechanism_questions(query: str) -> None:
    assert is_mechanism_query(query)


def test_location_follow_up_is_not_a_mechanism_question() -> None:
    assert not is_mechanism_query("Peki bu hangi dosyada?")
