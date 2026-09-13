import React, { useState } from 'react';
import { 
  Container, 
  TextField, 
  Button, 
  Box, 
  Typography, 
  Paper,
  CircularProgress} from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import axios from 'axios';

interface Message {
  text: string;
  isUser: boolean;
  evidence?: Evidence[];
  abstained?: boolean;
}

interface Evidence {
  id: string;
  source: string;
  excerpt: string;
  page?: string | number | null;
}

interface AnswerResponse {
  answer: string;
  sources: string[];
  evidence: Evidence[];
  abstained: boolean;
}

const App: React.FC = () => {
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const API_ENDPOINT = process.env.REACT_APP_API_ENDPOINT || '/api/ask';
  

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;

    // ユーザーの質問をメッセージに追加
    const userMessage: Message = { text: question, isUser: true };
    setMessages(prev => [...prev, userMessage]);
    setQuestion('');
    setIsLoading(true);

    try {
      // バックエンドに質問を送信
      const response = await axios.post<AnswerResponse>(API_ENDPOINT, {
        question: question
      });

      // 回答をメッセージに追加
      const botMessage: Message = { 
        text: response.data.answer,
        isUser: false,
        evidence: response.data.evidence,
        abstained: response.data.abstained,
      };
      setMessages(prev => [...prev, botMessage]);
    } catch (error) {
      console.error('Error:', error);
      const errorMessage: Message = { 
        text: '申し訳ありません。エラーが発生しました。', 
        isUser: false 
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Container maxWidth="md" sx={{ py: 4 }}>
      <Typography variant="h4" component="h1" gutterBottom align="center">
        QAbot
      </Typography>
      
      <Paper 
        elevation={3} 
        sx={{ 
          height: '60vh', 
          overflow: 'auto', 
          mb: 2, 
          p: 2,
          display: 'flex',
          flexDirection: 'column',
          gap: 2
        }}
      >
        {messages.map((message, index) => (
          <Box
            key={index}
            sx={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: message.isUser ? 'flex-end' : 'flex-start',
            }}
          >
            <Paper
              sx={{
                p: 2,
                maxWidth: '70%',
                backgroundColor: message.isUser ? '#e3f2fd' : '#f5f5f5',
              }}
            >
              {message.abstained ? <Typography color="text.secondary">回答保留</Typography> : null}
              <Typography sx={{ whiteSpace: 'pre-wrap' }}>{message.text}</Typography>
              {message.evidence?.map(item => (
                <Box component="details" key={item.id} sx={{ mt: 1 }}>
                  <Box component="summary" sx={{ cursor: 'pointer', overflowWrap: 'anywhere' }}>
                    参照資料: {item.source}{item.page != null ? ` / ページ ${item.page}` : ''}
                  </Box>
                  <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', mt: 1, overflowWrap: 'anywhere' }}>
                    {item.excerpt}
                  </Typography>
                </Box>
              ))}
            </Paper>
          </Box>
        ))}
        {isLoading && (
          <Box sx={{ display: 'flex', justifyContent: 'center' }}>
            <CircularProgress />
          </Box>
        )}
      </Paper>

      <form onSubmit={handleSubmit}>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <TextField
            fullWidth
            variant="outlined"
            placeholder="質問を入力してください..."
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            disabled={isLoading}
          />
          <Button
            type="submit"
            variant="contained"
            color="primary"
            disabled={isLoading || !question.trim()}
            sx={{ minWidth: '100px' }}
          >
            <SendIcon />
          </Button>
        </Box>
      </form>
    </Container>
  );
};

export default App;
