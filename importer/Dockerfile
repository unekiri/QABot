# マルチステージビルド: importerサービス用
FROM python:3.12-slim as builder

WORKDIR /build

# ビルド専用依存関係
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --user -r requirements.txt

# 実行用最小イメージ
FROM python:3.12-slim as runtime

WORKDIR /app

# セキュリティ: 非rootユーザー作成
RUN useradd --create-home --shell /bin/bash importer

# ビルド成果物をコピー
COPY --from=builder /root/.local /home/importer/.local

# アプリケーション実行権限設定
COPY . .
RUN chown -R importer:importer /app

USER importer
ENV PATH=/home/importer/.local/bin:$PATH

# データボリューム用ディレクトリ
VOLUME ["/app/documents", "/app/logs"]

CMD ["python", "docsImporter.py"]