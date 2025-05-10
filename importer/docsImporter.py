import shutil
import chromadb
from langchain.text_splitter import RecursiveCharacterTextSplitter
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
        collection.add(
            ids=[f"doc{i}" for i in range(len(docs))],
            documents=[d.page_content for d in docs],
            embeddings=emb.embed_documents([d.page_content for d in docs]),
            metadatas=[{"source": d.metadata.get("source", "")} for d in docs],
        )
        
        print(f"✅ {collection.count()} 個のチャンクが埋め込まれました。")

        # 処理済みファイルをLogsフォルダに移動
        print("📂 処理済みファイルをLogsフォルダに移動しています...")
        logs_dir = Path(__file__).parent / "logs"
        logs_dir.mkdir(exist_ok=True)  # Logsフォルダが存在しない場合は作成

        for doc in raw_docs:
            source_path = Path(doc.metadata.get("source", ""))
            if source_path.exists():
                dest_path = logs_dir / source_path.name
                shutil.move(str(source_path), str(dest_path))
                print(f"  ✓ {source_path.name} を移動しました")
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {str(e)}")

if __name__ == "__main__":
    main() 