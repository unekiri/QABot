from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import chromadb
from sentence_transformers import SentenceTransformer
import ollama
import os
import logging
from rag import select_evidence, create_prompt, parse_answer, ANSWER_SCHEMA, NO_EVIDENCE
from config import (
    API_HOST,
    API_PORT,
    CHROMA_HOST,
    CHROMA_PORT,
    COLLECTION_NAME,
    EMBEDDING_MODEL,
    LLM_MODEL,
    OLLAMA_HOST,
    OLLAMA_PORT,
    CHUNK_SIZE,
    CHUNK_OVERLAP
)

logger = logging.getLogger(__name__)
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_, __):
    return JSONResponse(status_code=422, content={"detail": "Invalid request"})

# リクエストモデル
class QuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)

# レスポンスモデル
class Evidence(BaseModel):
    id: str
    source: str
    excerpt: str
    page: str | int | None = None


class AnswerResponse(BaseModel):
    answer: str
    sources: list[str]
    evidence: list[Evidence]
    abstained: bool = False

# ChromaDBクライアントの初期化
client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
collection = client.get_or_create_collection(COLLECTION_NAME)

# 埋め込みモデルの初期化
embeddings = SentenceTransformer(EMBEDDING_MODEL)

# Ollamaクライアントの初期化
ollama_client = ollama.Client(host=f"http://{OLLAMA_HOST}:{OLLAMA_PORT}")

@app.get("/health")
async def health():
    """ヘルスチェックエンドポイント"""
    return {"status": "healthy"}

@app.post("/api/ask", response_model=AnswerResponse)
async def ask_question(request: QuestionRequest):
    try:
        document_count = collection.count()
        if not request.question.strip() or document_count == 0:
            return AnswerResponse(answer=NO_EVIDENCE, sources=[], evidence=[], abstained=True)
        # 質問の埋め込みを生成
        question_embedding = embeddings.encode(request.question).tolist()
        
        # ChromaDBから関連ドキュメントを検索
        results = collection.query(
            query_embeddings=[question_embedding],
            n_results=min(3, document_count),
            include=['documents', 'metadatas', 'embeddings']
        )
        
        # 検索結果から関連ドキュメントを取得
        evidence = select_evidence(
            results, question_embedding,
            float(os.getenv('MIN_RELEVANCE', '0.8')),
        )
        if not evidence:
            return AnswerResponse(answer=NO_EVIDENCE, sources=[], evidence=[], abstained=True)
        
        # プロンプトの作成
        prompt = create_prompt(request.question, evidence)
        # LLMにプロンプトを送信
        response = ollama_client.generate(
            model=LLM_MODEL, prompt=prompt, format=ANSWER_SCHEMA,
            options={'temperature': 0},
        )
        answer, abstained = parse_answer(response['response'], evidence)
        
        return AnswerResponse(
            answer=NO_EVIDENCE if abstained else answer,
            sources=list(dict.fromkeys(item['source'] for item in evidence)),
            evidence=evidence,
            abstained=abstained,
        )
        
    except Exception:
        logger.exception("Question processing failed")
        raise HTTPException(status_code=500, detail="Internal server error")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=API_HOST, port=API_PORT)
