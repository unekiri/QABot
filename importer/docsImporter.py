from collections import defaultdict
from indexing import index_document
import chromadb
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
     DirectoryLoader,
     UnstructuredFileLoader,
 )
from langchain_community.embeddings import SentenceTransformerEmbeddings
from config import (
    DOC_DIR,
    CHROMA_HOST,
    CHROMA_PORT,
    COLLECTION_NAME,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    EMBEDDING_MODEL
)
from pathlib import Path

def main():
    try:
        # ドキュメントの読み込み
        print("📚 ドキュメントを読み込んでいます...")
        loader = DirectoryLoader(str(DOC_DIR), loader_cls=UnstructuredFileLoader)
        raw_docs = loader.load()
        
        # テキストの分割
        print("✂️ テキストを分割しています...")
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP
        )
        docs = splitter.split_documents(raw_docs)
        
        # 埋め込みモデルの初期化
        print("🤖 埋め込みモデルを初期化しています...")
        emb = SentenceTransformerEmbeddings(model_name=EMBEDDING_MODEL)
        
        # ChromaDBクライアントの初期化
        print("🔌 ChromaDBに接続しています...")
        client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
        collection = client.get_or_create_collection(COLLECTION_NAME)
        
        # ドキュメントの追加
        print("📥 ドキュメントをデータベースに追加しています...")
        grouped = defaultdict(list)
        for doc in docs:
            source = doc.metadata.get('source')
            if not source:
                raise ValueError('Document source is missing')
            grouped[source].append(doc)
        logs_dir = Path(__file__).parent / "logs"
        for source, chunks in grouped.items():
            count = index_document(collection, emb.embed_documents, chunks,
                                   source, DOC_DIR, logs_dir)
            print(f"✅ {source}: {count} 個のチャンクを登録・照合しました。")
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {str(e)}")
        raise

if __name__ == "__main__":
    main()
