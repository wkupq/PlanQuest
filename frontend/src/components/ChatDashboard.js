import React, { useState, useRef, useEffect } from 'react';

const API_BASE = 'http://127.0.0.1:8000/api';

export default function ChatDashboard({ onClose }) {
  const [messages, setMessages] = useState([
    { id: 1, type: 'bot', text: '안녕하세요! 🤖 AI 비서입니다. 무엇을 도와드릴까요?' },
  ]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [ollamaStatus, setOllamaStatus] = useState(null); // null | true | false
  const messagesEndRef = useRef(null);
  const abortRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => { scrollToBottom(); }, [messages]);

  // Ollama 상태 확인
  useEffect(() => {
    checkOllamaHealth();
  }, []);

  const checkOllamaHealth = async () => {
    try {
      const res = await fetch(`${API_BASE}/chat/health`);
      const data = await res.json();
      setOllamaStatus(data.ollama_running);
    } catch {
      setOllamaStatus(false);
    }
  };

  const handleSend = async () => {
    if (!input.trim() || isStreaming) return;

    const userMsg = { id: Date.now(), type: 'user', text: input };
    const botMsgId = Date.now() + 1;

    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setIsStreaming(true);

    // 빈 봇 메시지 추가 (스트리밍으로 채워짐)
    setMessages((prev) => [...prev, { id: botMsgId, type: 'bot', text: '', streaming: true }]);

    try {
      const controller = new AbortController();
      abortRef.current = controller;

      const response = await fetch(`${API_BASE}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: input }),
        signal: controller.signal,
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let accumulated = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const jsonStr = line.slice(6).trim();
          if (!jsonStr) continue;

          try {
            const data = JSON.parse(jsonStr);

            if (data.done) {
              // 스트리밍 완료
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === botMsgId ? { ...m, streaming: false } : m
                )
              );
              break;
            }

            if (data.token) {
              accumulated += data.token;
              const currentText = accumulated;
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === botMsgId ? { ...m, text: currentText } : m
                )
              );
            }
          } catch {
            // JSON 파싱 실패 무시
          }
        }
      }
    } catch (err) {
      if (err.name === 'AbortError') {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === botMsgId ? { ...m, text: m.text + '\n\n(중단됨)', streaming: false } : m
          )
        );
      } else {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === botMsgId
              ? { ...m, text: '❌ 서버 연결에 실패했습니다. 백엔드가 실행 중인지 확인해주세요.', streaming: false }
              : m
          )
        );
      }
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
    }
  };

  const handleStop = () => {
    if (abortRef.current) {
      abortRef.current.abort();
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxHeight: '80vh', display: 'flex', flexDirection: 'column' }}>
        <div className="modal-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>🤖 AI 비서 채팅</span>
          <span style={{
            fontSize: '11px',
            padding: '3px 8px',
            borderRadius: '10px',
            background: ollamaStatus ? '#d4edda' : '#f8d7da',
            color: ollamaStatus ? '#155724' : '#721c24',
          }}>
            {ollamaStatus === null ? '확인 중...' : ollamaStatus ? '🟢 Ollama 연결됨' : '🔴 Ollama 미연결'}
          </span>
        </div>

        {/* Ollama 미연결 안내 */}
        {ollamaStatus === false && (
          <div style={{
            background: '#FFF3CD', border: '1px solid #FFEAA7', borderRadius: '8px',
            padding: '10px 14px', marginBottom: '8px', fontSize: '12px', color: '#856404',
          }}>
            ⚠️ Ollama가 연결되지 않았습니다. 채팅은 가능하지만 AI 응답을 받으려면 Ollama를 실행해주세요.
          </div>
        )}

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
                  whiteSpace: 'pre-wrap',
                }}
              >
                {msg.text}
                {msg.streaming && <span className="streaming-cursor">▌</span>}
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        <div style={{ display: 'flex', gap: '8px' }}>
          <input
            className="form-input"
            placeholder={isStreaming ? 'AI가 응답 중...' : '메시지를 입력하세요...'}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSend()}
            disabled={isStreaming}
            style={{ flex: 1, margin: 0 }}
          />
          {isStreaming ? (
            <button
              style={{
                padding: '10px 16px', borderRadius: '10px', border: 'none',
                background: '#e74c3c', color: 'white', cursor: 'pointer',
                fontWeight: '500', fontSize: '14px',
              }}
              onClick={handleStop}
            >
              중지
            </button>
          ) : (
            <button
              style={{
                padding: '10px 16px', borderRadius: '10px', border: 'none',
                background: '#5D8A5D', color: 'white', cursor: 'pointer',
                fontWeight: '500', fontSize: '14px',
              }}
              onClick={handleSend}
            >
              전송
            </button>
          )}
        </div>

        <button className="cancel-btn" onClick={onClose} style={{ marginTop: '12px' }}>닫기</button>
      </div>
    </div>
  );
}
