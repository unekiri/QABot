# マルチステージビルド: importerサービス用
FROM python:3.12-slim AS builder

WORKDIR /build
ARG EMBEDDING_MODEL=intfloat/multilingual-e5-large
ENV HF_HOME=/opt/huggingface

# ビルド専用依存関係
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --user --no-deps \
        torch==2.7.1+cpu --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir --user -r requirements.txt
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${EMBEDDING_MODEL}')"
RUN python -c "from unstructured.partition.text import partition_text; partition_text(text='これはオフライン実行に必要な文章分割モデルを準備するための文です。')"

# 実行用最小イメージ
FROM python:3.12-slim AS runtime

WORKDIR /app

# セキュリティ: 非rootユーザー作成
RUN useradd --create-home --shell /bin/bash importer

# ビルド成果物をコピー
COPY --from=builder /root/.local /home/importer/.local
COPY --from=builder /opt/huggingface /opt/huggingface
COPY --from=builder /usr/local/lib/python3.12/site-packages/en_core_web_sm /usr/local/lib/python3.12/site-packages/en_core_web_sm
COPY --from=builder /usr/local/lib/python3.12/site-packages/en_core_web_sm-3.8.0.dist-info /usr/local/lib/python3.12/site-packages/en_core_web_sm-3.8.0.dist-info

# アプリケーション実行権限設定
COPY . .
RUN chown -R importer:importer /app

USER importer
ENV PATH=/home/importer/.local/bin:$PATH
ENV HF_HOME=/opt/huggingface \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    ANONYMIZED_TELEMETRY=False

# データボリューム用ディレクトリ
VOLUME ["/app/documents", "/app/logs"]

CMD ["python", "docsImporter.py"]
