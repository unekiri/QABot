import React, { useState } from 'react';
import { 
  Container, 
  TextField, 
  Button, 
  Box, 
  Typography, 
  Paper,
  CircularProgress,
  List,
  ListItem,
  ListItemText
} from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import axios from 'axios';

interface Message {
  text: string;
  isUser: boolean;
  sources?: string[];
}

const App: React.FC = () => {
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);

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
      const response = await axios.post('http://host.docker.internal:5000/api/ask', {
        question: question
      });

      // 回答をメッセージに追加
      const botMessage: Message = { 
        text: response.data.answer,
        isUser: false,
        sources: response.data.sources
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
        検索チャット
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
              <Typography>{message.text}</Typography>
              {!message.isUser && message.sources && message.sources.length > 0 && (
                <Box sx={{ mt: 2 }}>
                  <Typography variant="subtitle2" color="text.secondary">
                    参考資料:
                  </Typography>
                  <List dense>
                    {message.sources.map((source, idx) => (
                      <ListItem key={idx}>
                        <ListItemText
                          primary={source}
                          primaryTypographyProps={{ variant: 'body2' }}
                        />
                      </ListItem>
                    ))}
                  </List>
                </Box>
              )}
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