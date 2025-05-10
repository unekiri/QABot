from fastapi.testclient import TestClient
from main import app
import pytest

client = TestClient(app)

def test_health_check():
    """ヘルスチェックエンドポイントのテスト"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_ask_endpoint_success():
    """質問応答エンドポイントの正常系テスト"""
    test_question = "テスト質問"
    response = client.post(
        "/api/ask",
        json={"question": test_question}
    )
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "sources" in data
    assert isinstance(data["sources"], list)

def test_ask_endpoint_invalid_input():
    """質問応答エンドポイントの異常系テスト（不正な入力）"""
    # 空の質問
    response = client.post(
        "/api/ask",
        json={"question": ""}
    )
    assert response.status_code == 400

    # 質問が長すぎる
    long_question = "?" * 1001
    response = client.post(
        "/api/ask",
        json={"question": long_question}
    )
    assert response.status_code == 400

def test_ask_endpoint_missing_field():
    """質問応答エンドポイントの異常系テスト（必須フィールドの欠落）"""
    response = client.post(
        "/api/ask",
        json={}
    )
    assert response.status_code == 422
