import pytest
import os
import tempfile
from docsImporter import process_document, main

def test_process_document():
    """ドキュメント処理のテスト"""
    # テスト用の一時ファイルを作成
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
        temp_file.write("これはテストドキュメントです。\n重要な情報が含まれています。")
        temp_file_path = temp_file.name

    try:
        # ドキュメントを処理
        result = process_document(temp_file_path)
        
        # 結果の検証
        assert result is not None
        assert isinstance(result, dict)
        assert "content" in result
        assert "metadata" in result
        assert "source" in result["metadata"]
        assert result["metadata"]["source"] == temp_file_path
    finally:
        # 一時ファイルを削除
        os.unlink(temp_file_path)

def test_process_document_invalid_file():
    """無効なファイルの処理テスト"""
    with pytest.raises(FileNotFoundError):
        process_document("nonexistent_file.txt")

def test_process_document_empty_file():
    """空ファイルの処理テスト"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
        temp_file_path = temp_file.name

    try:
        result = process_document(temp_file_path)
        assert result is not None
        assert result["content"] == ""
    finally:
        os.unlink(temp_file_path)

def test_main_function():
    """メイン関数のテスト"""
    # テスト用の一時ディレクトリを作成
    with tempfile.TemporaryDirectory() as temp_dir:
        # テストファイルを作成
        test_file_path = os.path.join(temp_dir, "test.txt")
        with open(test_file_path, "w") as f:
            f.write("テストドキュメント")

        # メイン関数を実行
        main(input_dir=temp_dir)

        # ここでは実際のデータベース操作はモック化する必要があります
        # 実際の実装に応じて検証を追加してください 