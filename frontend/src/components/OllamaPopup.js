import React, { useState } from 'react';

const API_BASE = 'http://127.0.0.1:8000/api';

/**
 * Ollama 미설치/미실행 팝업
 * - 미설치: 설치 안내 + 다운로드 링크
 * - 미실행: 자동 시작 버튼
 * - 모델 없음: 자동 다운로드 버튼
 */
export default function OllamaPopup({ status, onClose, onRetry }) {
  const [setting, setSetting] = useState(false);
  const [setupResult, setSetupResult] = useState(null);

  const handleAutoSetup = async () => {
    setSetting(true);
    setSetupResult(null);
    try {
      const res = await fetch(`${API_BASE}/chat/setup-ollama`, { method: 'POST' });
      const data = await res.json();
      setSetupResult(data);
      if (data.running && data.model_available) {
        // 성공 → 잠시 후 팝업 닫고 새로고침
        setTimeout(() => {
          onRetry();
          onClose();
        }, 1500);
      }
    } catch {
      setSetupResult({ error: 'NETWORK_ERROR' });
    } finally {
      setSetting(false);
    }
  };

  // 미설치 상태
  if (!status.ollama_installed) {
    return (
      <div className="ollama-popup-overlay" onClick={onClose}>
        <div className="ollama-popup" onClick={(e) => e.stopPropagation()}>
          <h2>⚠️ Ollama 미설치</h2>
          <p>
            AI 채팅을 사용하려면 <strong>Ollama</strong>가 필요합니다.
          </p>
          <p style={{ marginTop: '12px' }}>
            아래 링크에서 Ollama를 설치한 뒤,<br />
            터미널에서 모델을 다운로드하세요:
          </p>
          <div style={{
            background: '#F5F0E8', borderRadius: '8px', padding: '12px',
            margin: '12px 0', fontFamily: 'monospace', fontSize: '13px',
            color: '#5D3A1A', textAlign: 'left',
          }}>
            <div style={{ marginBottom: '6px' }}>1. Ollama 설치:</div>
            <div style={{ marginLeft: '12px', marginBottom: '10px' }}>
              <a href="https://ollama.ai" target="_blank" rel="noopener noreferrer"
                style={{ color: '#2980b9' }}>
                https://ollama.ai
              </a>
            </div>
            <div style={{ marginBottom: '6px' }}>2. 모델 다운로드:</div>
            <code style={{ marginLeft: '12px' }}>ollama pull {status.model || 'llama3.2:latest'}</code>
          </div>
          <div className="ollama-popup-actions">
            <button className="secondary-btn" onClick={onClose}>나중에</button>
            <button className="primary-btn" onClick={onRetry}>다시 확인</button>
          </div>
        </div>
      </div>
    );
  }

  // 설치됨 but 미실행 or 모델 없음
  return (
    <div className="ollama-popup-overlay" onClick={onClose}>
      <div className="ollama-popup" onClick={(e) => e.stopPropagation()}>
        <h2>
          {!status.ollama_running ? '🔌 Ollama 미실행' : '📦 모델 미설치'}
        </h2>
        <p>
          {!status.ollama_running
            ? 'Ollama가 설치되어 있지만 서버가 실행되고 있지 않습니다.'
            : `모델 '${status.model}'이 아직 다운로드되지 않았습니다.`
          }
        </p>

        {setupResult && (
          <div style={{
            marginTop: '12px', padding: '10px', borderRadius: '8px',
            background: setupResult.running && setupResult.model_available ? '#d4edda' : '#f8d7da',
            color: setupResult.running && setupResult.model_available ? '#155724' : '#721c24',
            fontSize: '13px',
          }}>
            {setupResult.running && setupResult.model_available
              ? '✅ 설정 완료! 잠시 후 팝업이 닫힙니다...'
              : `❌ 설정 실패: ${setupResult.error || '알 수 없는 오류'}`
            }
          </div>
        )}

        <div className="ollama-popup-actions">
          <button className="secondary-btn" onClick={onClose}>나중에</button>
          <button
            className="primary-btn"
            onClick={handleAutoSetup}
            disabled={setting}
          >
            {setting ? '⏳ 설정 중...' : '🚀 자동 설정'}
          </button>
        </div>

        <p style={{ fontSize: '11px', color: '#999', marginTop: '14px' }}>
          또는 터미널에서 직접: <code>ollama serve</code>
        </p>
      </div>
    </div>
  );
}
