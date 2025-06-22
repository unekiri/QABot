# マルチステージビルド: 依存関係ビルド用
FROM python:3.12-slim as builder

WORKDIR /build

# ビルド依存関係のインストール
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --user -r requirements.txt

# 実行用イメージ
FROM python:3.12-slim as runtime

WORKDIR /app

# 必要最小限のランタイム依存関係
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash app

# ビルドステージから依存関係をコピー
COPY --from=builder /root/.local /home/app/.local

# アプリケーションコードをコピー
COPY . .
RUN chown -R app:app /app

# 非rootユーザーで実行
USER app
ENV PATH=/home/app/.local/bin:$PATH

# アプリケーションがリッスンするポートを公開
EXPOSE 5000

# コンテナ起動時に実行するコマンド
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]