from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import chromadb
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_community.llms import Ollama
from config import (
    API_HOST,
    API_PORT,
    CORS_ORIGINS,
    CHROMA_HOST,
    CHROMA_PORT,
    COLLECTION_NAME,
    EMBEDDING_MODEL,
    LLM_MODEL,
    CHUNK_SIZE,
    CHUNK_OVERLAP
)

app = FastAPI()

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# リクエストモデル
class QuestionRequest(BaseModel):
    question: str

# レスポンスモデル
class AnswerResponse(BaseModel):
    answer: str
    sources: list[str]

# ChromaDBクライアントの初期化
client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
collection = client.get_or_create_collection(COLLECTION_NAME)

# 埋め込みモデルの初期化
embeddings = SentenceTransformerEmbeddings(model_name=EMBEDDING_MODEL)

# LLMの初期化
llm = Ollama(model=LLM_MODEL)

@app.post("/api/ask", response_model=AnswerResponse)
async def ask_question(request: QuestionRequest):
    try:
        # 質問の埋め込みを生成
        question_embedding = embeddings.embed_query(request.question)
        
        # ChromaDBから関連ドキュメントを検索
        results = collection.query(
            query_embeddings=[question_embedding],
            n_results=3
        )
        
        # 検索結果から関連ドキュメントを取得
        relevant_docs = results['documents'][0]
        sources = results['metadatas'][0]
        
        # プロンプトの作成
        context = "\n\n".join(relevant_docs)
        prompt = f"""以下のコンテキストに基づいて、ユーザーの質問に答えてください。

コンテキスト:
{context}

ユーザーの質問: {request.question}

回答:"""
        
        # LLMにプロンプトを送信
        answer = llm.invoke(prompt)
        
        return AnswerResponse(
            answer=answer,
            sources=[source.get('source', '') for source in sources]
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=API_HOST, port=API_PORT) 