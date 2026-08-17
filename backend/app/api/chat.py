from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.api.dependencies import rag_service
from app.providers.chat import ChatProviderError
from app.providers.embeddings import EmbeddingProviderError
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.source import SourceResponse
from app.services.retrieval_service import (
    InvalidStoredEmbeddingError,
    ProjectNotFoundError,
    ProjectNotIndexedError,
)

router = APIRouter()


@router.post(
    "/projects/{project_id}/chat",
    response_model=ChatResponse,
    responses={503: {"model": ChatResponse}},
)
def chat_with_project(
    project_id: str,
    request: ChatRequest,
) -> ChatResponse | JSONResponse:
    try:
        result = rag_service.answer(
            project_id=project_id,
            question=request.question,
            top_k=request.top_k,
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except ProjectNotIndexedError:
        return ChatResponse(
            answer="Proje henüz indekslenmedi. Önce indeksleme işlemini tamamlayın.",
            answer_status="indexing_incomplete",
            sources=[],
        )
    except (EmbeddingProviderError, ChatProviderError):
        response = ChatResponse(
            answer="Yerel yapay zeka modeli şu anda kullanılamıyor.",
            answer_status="error",
            sources=[],
        )
        return JSONResponse(status_code=503, content=response.model_dump())
    except InvalidStoredEmbeddingError:
        response = ChatResponse(
            answer="Kayıtlı indeks geçersiz. Projeyi yeniden indeksleyin.",
            answer_status="error",
            sources=[],
        )
        return JSONResponse(status_code=500, content=response.model_dump())

    return ChatResponse(
        answer=result.answer,
        answer_status=result.answer_status,
        sources=[
            SourceResponse(
                chunk_id=item.chunk["id"],
                file_path=item.chunk["file_path"],
                language=item.chunk["language"],
                symbol_name=item.chunk["symbol_name"],
                symbol_type=item.chunk["symbol_type"],
                start_line=item.chunk["start_line"],
                end_line=item.chunk["end_line"],
                parse_status=item.chunk["parse_status"],
                score=item.score,
                snippet=item.chunk["content"],
            )
            for item in result.sources
        ],
    )
