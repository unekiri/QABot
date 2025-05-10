import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import App from './App';
import axios from 'axios';

// axiosのモック
jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

describe('App Component', () => {
  beforeEach(() => {
    // 各テスト前にモックをリセット
    jest.clearAllMocks();
  });

  test('初期表示時にチャットインターフェースが表示される', () => {
    render(<App />);
    
    // 入力フィールドが存在することを確認
    expect(screen.getByPlaceholderText('質問を入力してください')).toBeInTheDocument();
    
    // 送信ボタンが存在することを確認
    expect(screen.getByRole('button', { name: /送信/i })).toBeInTheDocument();
  });

  test('質問を入力して送信できる', async () => {
    // APIレスポンスのモック
    mockedAxios.post.mockResolvedValueOnce({
      data: {
        answer: 'テスト回答',
        sources: ['テストソース1', 'テストソース2']
      }
    });

    render(<App />);
    
    // 入力フィールドに質問を入力
    const input = screen.getByPlaceholderText('質問を入力してください');
    fireEvent.change(input, { target: { value: 'テスト質問' } });
    
    // 送信ボタンをクリック
    const sendButton = screen.getByRole('button', { name: /送信/i });
    fireEvent.click(sendButton);
    
    // ローディング表示を確認
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
    
    // APIが正しいパラメータで呼ばれたことを確認
    await waitFor(() => {
      expect(mockedAxios.post).toHaveBeenCalledWith(
        expect.stringContaining('/api/ask'),
        { question: 'テスト質問' }
      );
    });
    
    // 回答が表示されることを確認
    await waitFor(() => {
      expect(screen.getByText('テスト回答')).toBeInTheDocument();
    });
    
    // ソースが表示されることを確認
    expect(screen.getByText('テストソース1')).toBeInTheDocument();
    expect(screen.getByText('テストソース2')).toBeInTheDocument();
  });

  test('APIエラー時にエラーメッセージが表示される', async () => {
    // APIエラーのモック
    mockedAxios.post.mockRejectedValueOnce(new Error('API Error'));

    render(<App />);
    
    // 質問を送信
    const input = screen.getByPlaceholderText('質問を入力してください');
    fireEvent.change(input, { target: { value: 'テスト質問' } });
    fireEvent.click(screen.getByRole('button', { name: /送信/i }));
    
    // エラーメッセージが表示されることを確認
    await waitFor(() => {
      expect(screen.getByText(/エラーが発生しました/i)).toBeInTheDocument();
    });
  });
});
