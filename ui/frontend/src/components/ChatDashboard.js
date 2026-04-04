import React, { useState, useRef, useEffect } from 'react';

export default function ChatDashboard({ onClose }) {
  const [messages, setMessages] = useState([
    { id: 1, type: 'bot', text: '안녕하세요! 🤖 AI 비서입니다. 무엇을 도와드릴까요?' },
  ]);
  const [input, setInput] = useState('');
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => { scrollToBottom(); }, [messages]);

  const handleSend = () => {
    if (!input.trim()) return;

    // 사용자 메시지 추가
    const userMsg = { id: Date.now(), type: 'user', text: input };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');

    // 봇 응답 시뮬레이션 (실제로는 FastAPI AI 에이전트에 연결)
    setTimeout(() => {
      const responses = [
        '네, 이해했습니다! 📝',
        '좋은 일정을 실천하고 있네요! 👍',
        '계속 화이팅하세요! 💪',
        '오늘도 멋진 하루 되세요! ✨',
      ];
      const botMsg = {
        id: Date.now() + 1,
        type: 'bot',
        text: responses[Math.floor(Math.random() * responses.length)],
      };
      setMessages((prev) => [...prev, botMsg]);
    }, 500);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxHeight: '80vh', display: 'flex', flexDirection: 'column' }}>
        <div className="modal-title">🤖 AI 비서 채팅</div>

        <div style={{
          flex: 1,
          overflowY: 'auto',
          marginBottom: '12px',
          padding: '12px 0',
          display: 'flex',
          flexDirection: 'column',
          gap: '8px',
        }}>
          {messages.map((msg) => (
            <div
              key={msg.id}
              style={{
                display: 'flex',
                justifyContent: msg.type === 'user' ? 'flex-end' : 'flex-start',
                marginBottom: '8px',
              }}
            >
              <div
                style={{
                  maxWidth: '70%',
                  padding: '10px 14px',
                  borderRadius: msg.type === 'user' ? '14px 14px 0 14px' : '14px 14px 14px 0',
                  background: msg.type === 'user' ? '#5D8A5D' : '#E8D5B8',
                  color: msg.type === 'user' ? 'white' : '#5D3A1A',
                  fontSize: '14px',
                  wordBreak: 'break-word',
                  lineHeight: '1.4',
                }}
              >
                {msg.text}
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        <div style={{ display: 'flex', gap: '8px' }}>
          <input
            className="form-input"
            placeholder="메시지를 입력하세요..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSend()}
            style={{ flex: 1, margin: 0 }}
          />
          <button
            style={{
              padding: '10px 16px',
              borderRadius: '10px',
              border: 'none',
              background: '#5D8A5D',
              color: 'white',
              cursor: 'pointer',
              fontWeight: '500',
              fontSize: '14px',
            }}
            onClick={handleSend}
          >
            전송
          </button>
        </div>

        <button className="cancel-btn" onClick={onClose} style={{ marginTop: '12px' }}>닫기</button>
      </div>
    </div>
  );
}
