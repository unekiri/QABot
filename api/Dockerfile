# マルチステージビルド: 依存関係ビルド用
FROM python:3.12-slim AS builder

WORKDIR /build
ARG EMBEDDING_MODEL=intfloat/multilingual-e5-large
ENV HF_HOME=/opt/huggingface

# ビルド依存関係のインストール
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

# 実行用イメージ
FROM python:3.12-slim AS runtime

WORKDIR /app

# 非root実行ユーザー
RUN useradd --create-home --shell /bin/bash app

# ビルドステージから依存関係をコピー
COPY --from=builder /root/.local /home/app/.local
COPY --from=builder /opt/huggingface /opt/huggingface

# アプリケーションコードをコピー
COPY . .
RUN chown -R app:app /app

# 非rootユーザーで実行
USER app
ENV PATH=/home/app/.local/bin:$PATH
ENV HF_HOME=/opt/huggingface \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    ANONYMIZED_TELEMETRY=False

# アプリケーションがリッスンするポートを公開
EXPOSE 5000

# コンテナ起動時に実行するコマンド
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]
