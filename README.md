# QABot

ドキュメントを学習し、質問に回答するチャットボットシステムです。

## 主な機能

- ドキュメントのインポートとベクトルデータベースへの保存
- 自然言語での質問応答
- 外部検索エンジンとの連携

## クイックスタート

1. リポジトリのクローン
```bash
git clone <repository-url>
cd TrainingChatBot
```

2. Ollamaの起動
```bash
# Ollamaの起動
ollama serve

# 必要なモデルのダウンロード
ollama pull gemma3:1b
```

3. 環境変数の設定
```bash
cp .env.example .env
```

4. Docker Composeで起動
```bash
docker compose up -d
```

以下のサービスが起動します：
- APIサーバー (http://localhost:5000)
- ChromaDB (http://localhost:8000)
- Nginx (http://localhost:8080)

## 使用方法

### ドキュメントのインポート

```bash
# インポーターの実行
python importer/main.py --input-dir /path/to/documents
```

### APIの使用

APIは以下のエンドポイントを提供します：

- `GET /health`: ヘルスチェック
  ```bash
  curl http://localhost:8080/health
  ```

- `POST /api/ask`: 質問を送信し、回答を受け取る
  ```bash
  curl -X POST "http://localhost:8080/api/ask" \
       -H "Content-Type: application/json" \
       -d '{"question": "あなたの質問"}'
  ```

## コンテナ構成

| サービス | 説明 | ポート | イメージ |
|----------|------|--------|----------|
| api | FastAPIアプリケーション | 5000 | カスタムビルド |
| chroma | ベクトルデータベース | 8000 | chromadb/chroma:latest |
| nginx | リバースプロキシ | 8080 | nginx:latest |

## プロジェクト構造

```
TrainingChatBot/
├── api/                    # APIサーバー
│   ├── main.py            # FastAPIアプリケーション
│   ├── Dockerfile         # APIサーバーのDockerfile
│   └── requirements.txt   # 依存パッケージ
├── importer/              # ドキュメントインポーター
│   ├── main.py           # インポータースクリプト
│   └── requirements.txt  # 依存パッケージ
├── nginx/                 # Nginx設定
│   ├── nginx.conf        # メインのNginx設定
│   └── conf.d/           # 追加のNginx設定
├── tests/                # テストディレクトリ
│   └── test_main.py     # APIテスト
├── .env.example         # 環境変数のサンプル
├── docker-compose.yml   # Docker Compose設定
└── README.md
```

## 開発

# APIテストの実行
cd api
pytest tests/test_main.py -v
```

### 依存パッケージのインストール（開発用）

```bash
# 仮想環境の作成
python -m venv venv
source venv/bin/activate  # Linuxの場合
.\venv\Scripts\activate   # Windowsの場合

# APIサーバー
cd api
pip install -r requirements.txt

# インポーター
cd ../importer
pip install -r requirements.txt
```

## セキュリティ

- 環境変数は`.env`ファイルで管理し、Gitにコミットしないでください
- 本番環境では適切な認証・認可の設定を行ってください
- 定期的に依存パッケージのアップデートを行ってください

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。詳細は[LICENSE](LICENSE)ファイルを参照してください。
