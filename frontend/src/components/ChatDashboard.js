import React, { useState, useRef, useEffect, useCallback } from 'react';

const API_BASE = 'http://127.0.0.1:8000/api';
const STORAGE_KEY = 'planquest_chat_history';
const MAX_HISTORY = 100; // 최대 저장 메시지 수
const WELCOME_MSG = {
  id: 1,
  type: 'bot',
  text: '안녕하세요! 🤖 AI 비서입니다.\n일정 확인, 메일 검색, 일정 등록 등을 도와드릴게요.\n\n예시:\n- "오늘 일정 알려줘"\n- "skala 메일 있어?"\n- "내일 오전 10시에 회의 일정 추가해줘"',
};

function loadMessages() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [WELCOME_MSG];
    const parsed = JSON.parse(raw);
    return parsed.map((m) => ({ ...m, streaming: false }));
  } catch {
    return [WELCOME_MSG];
  }
}

/** 일정 등록 확인 메시지 감지 */
function isScheduleConfirm(text) {
  return text.includes('✅') && text.includes('일정이 등록됐어요');
}

/** 텍스트를 줄바꿈 기준으로 분리해 렌더링 */
function MessageText({ text }) {
  const lines = text.split('\n');
  return (
    <>
      {lines.map((line, i) => (
        <span key={i}>
          {line}
          {i < lines.length - 1 && <br />}
        </span>
      ))}
    </>
  );
}

export default function ChatDashboard({ onClose, onScheduleCreated }) {
  const [messages, setMessages] = useState(loadMessages);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [ollamaStatus, setOllamaStatus] = useState(null);
  const messagesEndRef = useRef(null);
  const abortRef = useRef(null);
  const inputRef = useRef(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => { scrollToBottom(); }, [messages, scrollToBottom]);

  // 스트리밍 완료된 메시지만 저장 (최대 MAX_HISTORY개)
  useEffect(() => {
    const toSave = messages
      .filter((m) => !m.streaming)
      .slice(-MAX_HISTORY);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(toSave));
    } catch {
      // 용량 초과 시 오래된 메시지 제거 후 재시도
      try {
        const trimmed = toSave.slice(-Math.floor(MAX_HISTORY / 2));
        localStorage.setItem(STORAGE_KEY, JSON.stringify(trimmed));
      } catch {
        // 무시
      }
    }
  }, [messages]);

  useEffect(() => { checkOllamaHealth(); }, []);

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

    const userText = input.trim();
    const userMsg = { id: Date.now(), type: 'user', text: userText };
    const botMsgId = Date.now() + 1;

    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setIsStreaming(true);

    setMessages((prev) => [
      ...prev,
      { id: botMsgId, type: 'bot', text: '', streaming: true },
    ]);

    try {
      const controller = new AbortController();
      abortRef.current = controller;

      const response = await fetch(`${API_BASE}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userText }),
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new Error(`서버 오류: ${response.status}`);
      }

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
              let scheduleCreated = false;
              setMessages((prev) =>
                prev.map((m) => {
                  if (m.id !== botMsgId) return m;
                  // 스트리밍 완료 시 __CREATE__ 태그 및 이후 내용 제거
                  const cleanText = m.text
                    .replace(/__CREATE__[\s\S]*$/g, '')
                    .replace(/\s*-\s*$/g, '')   // 끝에 남은 단독 하이픈 제거
                    .trim();
                  // 일정 등록 확인 메시지 감지 → App에 새로고침 요청
                  if (isScheduleConfirm(cleanText)) {
                    scheduleCreated = true;
                  }
                  return { ...m, text: cleanText, streaming: false };
                })
              );
              // 일정이 등록됐으면 App의 habits/trees 데이터 새로고침
              if (scheduleCreated && onScheduleCreated) {
                setTimeout(() => onScheduleCreated(), 300);
              }
              break;
            }

            if (data.error) {
              const errText = `오류가 발생했어요: ${data.error}`;
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === botMsgId
                    ? { ...m, text: errText, streaming: false }
                    : m
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
            // JSON 파싱 실패 — 무시
          }
        }
      }
    } catch (err) {
      if (err.name === 'AbortError') {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === botMsgId
              ? { ...m, text: m.text + '\n\n(응답 중단됨)', streaming: false }
              : m
          )
        );
      } else {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === botMsgId
              ? {
                  ...m,
                  text: '❌ 서버 연결에 실패했어요. 백엔드가 실행 중인지 확인해주세요.',
                  streaming: false,
                }
              : m
          )
        );
      }
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
      // 전송 후 입력창 포커스
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  };

  const handleStop = () => {
    if (abortRef.current) abortRef.current.abort();
  };

  const handleClearHistory = () => {
    if (!window.confirm('채팅 내역을 모두 삭제할까요?')) return;
    localStorage.removeItem(STORAGE_KEY);
    setMessages([WELCOME_MSG]);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-content"
        onClick={(e) => e.stopPropagation()}
        style={{ maxHeight: '85vh', display: 'flex', flexDirection: 'column' }}
      >
        {/* 헤더 */}
        <div
          className="modal-title"
          style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
        >
          <span>🤖 AI 비서 채팅</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <button
              onClick={handleClearHistory}
              title="채팅 내역 삭제"
              style={{
                fontSize: '11px', padding: '3px 8px', borderRadius: '10px',
                background: '#f0f0f0', color: '#666', border: '1px solid #ccc',
                cursor: 'pointer',
              }}
            >
              🗑 내역 삭제
            </button>
            <span
              style={{
                fontSize: '11px', padding: '3px 8px', borderRadius: '10px',
                background: ollamaStatus ? '#d4edda' : '#f8d7da',
                color: ollamaStatus ? '#155724' : '#721c24',
              }}
            >
              {ollamaStatus === null ? '확인 중...' : ollamaStatus ? '🟢 Ollama 연결됨' : '🔴 Ollama 미연결'}
            </span>
          </div>
        </div>

        {/* Ollama 미연결 안내 */}
        {ollamaStatus === false && (
          <div
            style={{
              background: '#FFF3CD', border: '1px solid #FFEAA7', borderRadius: '8px',
              padding: '10px 14px', marginBottom: '8px', fontSize: '12px', color: '#856404',
            }}
          >
            ⚠️ Ollama가 연결되지 않았습니다. AI 응답을 받으려면 터미널에서{' '}
            <code style={{ background: '#fff', padding: '1px 4px', borderRadius: '3px' }}>
              ollama serve
            </code>
            를 실행해주세요.
          </div>
        )}

        {/* 메시지 목록 */}
        <div
          style={{
            flex: 1, overflowY: 'auto', marginBottom: '12px',
            padding: '12px 4px', display: 'flex', flexDirection: 'column', gap: '8px',
          }}
        >
          {messages.map((msg) => {
            const isConfirm = msg.type === 'bot' && isScheduleConfirm(msg.text);
            return (
              <div
                key={msg.id}
                style={{
                  display: 'flex',
                  justifyContent: msg.type === 'user' ? 'flex-end' : 'flex-start',
                }}
              >
                <div
                  style={{
                    maxWidth: '78%',
                    padding: '10px 14px',
                    borderRadius:
                      msg.type === 'user' ? '14px 14px 0 14px' : '14px 14px 14px 0',
                    background: isConfirm
                      ? '#d4edda'                          // 일정 등록 확인 — 초록
                      : msg.type === 'user'
                      ? '#5D8A5D'                          // 사용자 — 초록
                      : '#E8D5B8',                         // 봇 — 베이지
                    color: isConfirm
                      ? '#155724'
                      : msg.type === 'user'
                      ? 'white'
                      : '#5D3A1A',
                    fontSize: '14px',
                    lineHeight: '1.6',
                    wordBreak: 'break-word',
                    border: isConfirm ? '1px solid #c3e6cb' : 'none',
                  }}
                >
                  <MessageText text={msg.text} />
                  {msg.streaming && (
                    <span
                      style={{
                        display: 'inline-block',
                        width: '2px', height: '14px',
                        background: '#5D3A1A',
                        marginLeft: '2px',
                        animation: 'blink 1s step-end infinite',
                        verticalAlign: 'text-bottom',
                      }}
                    />
                  )}
                </div>
              </div>
            );
          })}
          <div ref={messagesEndRef} />
        </div>

        {/* 입력창 */}
        <div style={{ display: 'flex', gap: '8px' }}>
          <input
            ref={inputRef}
            className="form-input"
            placeholder={
              isStreaming
                ? 'AI가 응답 중... (Enter로 중지 가능)'
                : '메시지를 입력하세요... (Shift+Enter: 줄바꿈)'
            }
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isStreaming}
            style={{ flex: 1, margin: 0 }}
          />
          {isStreaming ? (
            <button
              onClick={handleStop}
              style={{
                padding: '10px 16px', borderRadius: '10px', border: 'none',
                background: '#e74c3c', color: 'white', cursor: 'pointer',
                fontWeight: '500', fontSize: '14px', whiteSpace: 'nowrap',
              }}
            >
              중지
            </button>
          ) : (
            <button
              onClick={handleSend}
              disabled={!input.trim()}
              style={{
                padding: '10px 16px', borderRadius: '10px', border: 'none',
                background: input.trim() ? '#5D8A5D' : '#aaa',
                color: 'white', cursor: input.trim() ? 'pointer' : 'default',
                fontWeight: '500', fontSize: '14px', whiteSpace: 'nowrap',
              }}
            >
              전송
            </button>
          )}
        </div>

        <button className="cancel-btn" onClick={onClose} style={{ marginTop: '12px' }}>
          닫기
        </button>
      </div>

      {/* 커서 깜박임 애니메이션 */}
      <style>{`
        @keyframes blink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0; }
        }
      `}</style>
    </div>
  );
}
