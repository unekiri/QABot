FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt requirements.txt

# 依存関係をインストール
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --trusted-host pypi.python.org -r requirements.txt

# アプリケーションコードをコピー
COPY . .

# アプリケーションがリッスンするポートを公開
EXPOSE 5000

# コンテナ起動時に実行するコマンド
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]