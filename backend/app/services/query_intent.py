import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher


@dataclass(frozen=True, slots=True)
class OperationIntent:
    terms: frozenset[str]
    operator: str
    english_name: str
    turkish_name: str
    ambiguous_terms: frozenset[str] = frozenset()


ARITHMETIC_CONTEXT_TERMS = frozenset(
    {
        "arithmetic",
        "calculator",
        "math",
        "number",
        "numbers",
        "operand",
        "operands",
        "operation",
        "sum",
        "total",
        "value",
        "values",
        "hesap",
        "hesaplama",
        "islem",
        "islemi",
        "sayi",
        "sayilar",
    }
)


OPERATION_INTENTS = (
    OperationIntent(
        terms=frozenset(
            {
                "addition",
                "toplama",
                "topluyor",
                "toplaniyor",
            }
        ),
        operator="+",
        english_name="addition",
        turkish_name="toplama",
        ambiguous_terms=frozenset({"add", "adds", "adding"}),
    ),
    OperationIntent(
        terms=frozenset(
            {
                "subtraction",
                "subtract",
                "subtracts",
                "subtracting",
                "cikarma",
                "cikariyor",
                "cikariliyor",
            }
        ),
        operator="-",
        english_name="subtraction",
        turkish_name="çıkarma",
    ),
    OperationIntent(
        terms=frozenset(
            {
                "multiplication",
                "multiply",
                "multiplies",
                "multiplying",
                "carpma",
                "carpiyor",
                "carpiliyor",
            }
        ),
        operator="*",
        english_name="multiplication",
        turkish_name="çarpma",
    ),
    OperationIntent(
        terms=frozenset(
            {
                "division",
                "divide",
                "divides",
                "dividing",
                "bolme",
                "boluyor",
                "bolunuyor",
            }
        ),
        operator="/",
        english_name="division",
        turkish_name="bölme",
    ),
)


SCOPE_ROOTS = (
    "proje",
    "project",
    "repository",
    "application",
    "uygulama",
    "program",
    "yazilim",
    "codebase",
)
SCOPE_EXACT_TERMS = {
    "repo",
    "reponun",
    "repoyu",
    "repoya",
    "repoda",
    "repodaki",
    "kod",
    "kodu",
    "kodun",
    "kodda",
    "kodtabani",
    "kodtabaninin",
}
COMPONENT_ROOTS = (
    "api",
    "class",
    "component",
    "degisken",
    "dosya",
    "endpoint",
    "file",
    "fonksiyon",
    "function",
    "method",
    "metot",
    "module",
    "modul",
    "parser",
    "provider",
    "route",
    "router",
    "satir",
    "service",
    "servis",
    "sinif",
)
STRONG_OVERVIEW_ROOTS = (
    "about",
    "acikla",
    "amac",
    "anlat",
    "describe",
    "explain",
    "fayda",
    "gorev",
    "hakkinda",
    "konu",
    "overview",
    "ozet",
    "problem",
    "purpose",
    "summary",
    "tanit",
    "uzer",
)
QUESTION_TERMS = {"ne", "nedir", "neye", "neyin", "what", "whats"}
USEFULNESS_ROOTS = ("yar", "yap", "kullan", "do", "does", "work", "works")
HOW_OR_LOCATION_ROOTS = (
    "how",
    "implement",
    "nasil",
    "neye",
    "nerede",
    "uygula",
    "where",
)
FOLLOW_UP_REFERENCE_TERMS = {
    "above",
    "it",
    "its",
    "onceki",
    "same",
    "that",
    "them",
    "these",
    "they",
    "this",
    "those",
    "ona",
    "ondan",
    "onlar",
    "onlari",
    "onu",
    "onun",
    "peki",
}
FOLLOW_UP_REFERENCE_ROOTS = (
    "bahset",
    "bun",
    "islem",
    "ozellik",
    "sonuc",
    "yontem",
)
MECHANISM_QUERY_ROOTS = (
    "calis",
    "how",
    "nasil",
    "neden",
    "neye",
    "why",
)


def normalize_query(query: str) -> str:
    folded = query.casefold().replace("ı", "i")
    decomposed = unicodedata.normalize("NFKD", folded)
    without_marks = "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )
    return " ".join(re.findall(r"[a-z0-9]+", without_marks))


def tokenize_query(query: str) -> tuple[str, ...]:
    normalized = normalize_query(query)
    return tuple(normalized.split()) if normalized else ()


def _matches_root(token: str, root: str, *, allow_typo: bool = False) -> bool:
    if token.startswith(root):
        return True
    if not allow_typo or len(root) < 4:
        return False

    if abs(len(token) - len(root)) > 1:
        return False
    if not token or token[0] != root[0]:
        return False
    return SequenceMatcher(None, token, root).ratio() >= 0.78


def _matching_positions(
    tokens: tuple[str, ...],
    roots: tuple[str, ...],
    *,
    allow_typo: bool = False,
) -> list[int]:
    return [
        index
        for index, token in enumerate(tokens)
        if any(
            _matches_root(token, root, allow_typo=allow_typo)
            for root in roots
        )
    ]


def _scope_positions(tokens: tuple[str, ...]) -> list[int]:
    positions = _matching_positions(tokens, SCOPE_ROOTS, allow_typo=True)
    positions.extend(
        index
        for index, token in enumerate(tokens)
        if token in SCOPE_EXACT_TERMS
    )
    return sorted(set(positions))


def _nearest_distance(left: list[int], right: list[int]) -> int | None:
    if not left or not right:
        return None
    return min(abs(left_index - right_index) for left_index in left for right_index in right)


def _component_is_question_subject(
    scope_positions: list[int],
    component_positions: list[int],
    intent_anchor_positions: list[int],
) -> bool:
    component_distance = _nearest_distance(component_positions, intent_anchor_positions)
    scope_distance = _nearest_distance(scope_positions, intent_anchor_positions)
    return (
        component_distance is not None
        and scope_distance is not None
        and (
            component_distance < scope_distance
            or min(component_positions) < min(scope_positions)
        )
    )


def detect_operation(query: str) -> OperationIntent | None:
    words = set(tokenize_query(query))
    for intent in OPERATION_INTENTS:
        if any(
            _matches_root(word, term, allow_typo=True)
            for word in words
            for term in intent.terms
        ):
            return intent
        if words & intent.ambiguous_terms and words & ARITHMETIC_CONTEXT_TERMS:
            return intent
    return None


def is_project_overview_query(query: str) -> bool:
    tokens = tokenize_query(query)
    if not tokens:
        return False

    scope_positions = _scope_positions(tokens)
    if not scope_positions:
        return False

    component_positions = _matching_positions(tokens, COMPONENT_ROOTS)
    strong_positions = _matching_positions(
        tokens,
        STRONG_OVERVIEW_ROOTS,
        allow_typo=True,
    )
    question_positions = [
        index for index, token in enumerate(tokens) if token in QUESTION_TERMS
    ]
    usefulness_positions = _matching_positions(
        tokens,
        USEFULNESS_ROOTS,
        allow_typo=True,
    )
    how_positions = _matching_positions(tokens, ("how", "nasil"), allow_typo=True)
    work_positions = _matching_positions(tokens, ("calis", "work"), allow_typo=True)
    kind_positions = _matching_positions(tokens, ("bir", "kind", "type"))
    for_positions = [index for index, token in enumerate(tokens) if token == "for"]

    intent_anchor_positions = sorted(
        set(strong_positions + question_positions + how_positions)
    )
    if _component_is_question_subject(
        scope_positions,
        component_positions,
        intent_anchor_positions,
    ):
        return False

    if strong_positions:
        return True

    asks_what_it_does = bool(question_positions and usefulness_positions)
    asks_how_it_works = bool(how_positions and work_positions)
    asks_what_it_is_for = bool(question_positions and for_positions)
    asks_project_kind = bool(
        (question_positions and kind_positions)
        or (how_positions and kind_positions)
        or (
            question_positions
            and any(token.startswith("projesi") for token in tokens)
        )
    )
    return (
        asks_what_it_does
        or asks_how_it_works
        or asks_what_it_is_for
        or asks_project_kind
    )


def is_implementation_query(query: str) -> bool:
    if is_project_overview_query(query):
        return False

    tokens = tokenize_query(query)
    if not tokens:
        return False

    if _matching_positions(tokens, HOW_OR_LOCATION_ROOTS, allow_typo=True):
        return True

    component_positions = _matching_positions(tokens, COMPONENT_ROOTS)
    question_positions = [
        index for index, token in enumerate(tokens) if token in QUESTION_TERMS
    ]
    action_positions = _matching_positions(
        tokens,
        USEFULNESS_ROOTS,
        allow_typo=True,
    )
    which_positions = [
        index for index, token in enumerate(tokens) if token in {"hangi", "which"}
    ]
    return bool(
        component_positions
        and (question_positions or action_positions or which_positions)
    )


def is_context_dependent_query(query: str) -> bool:
    """Return whether a question likely needs a preceding conversational turn."""
    if is_project_overview_query(query):
        return False

    tokens = tokenize_query(query)
    if not tokens:
        return False

    if any(token in FOLLOW_UP_REFERENCE_TERMS for token in tokens):
        return True

    if any(
        _matches_root(token, root)
        for token in tokens
        for root in FOLLOW_UP_REFERENCE_ROOTS
    ) and detect_operation(query) is None:
        return True

    component_positions = _matching_positions(tokens, COMPONENT_ROOTS)
    question_positions = [
        index
        for index, token in enumerate(tokens)
        if token in QUESTION_TERMS or token in {"hangi", "which"}
    ]
    generic_terms = {
        "dosya",
        "dosyada",
        "file",
        "fonksiyon",
        "function",
        "hangi",
        "nerede",
        "which",
        "where",
    }
    return bool(
        len(tokens) <= 4
        and component_positions
        and question_positions
        and all(
            token in generic_terms
            or any(_matches_root(token, root) for root in COMPONENT_ROOTS)
            for token in tokens
        )
    )


def is_mechanism_query(query: str) -> bool:
    tokens = tokenize_query(query)
    return any(
        _matches_root(token, root, allow_typo=True)
        for token in tokens
        for root in MECHANISM_QUERY_ROOTS
    )
