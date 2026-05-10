import React, { useState, useEffect, useCallback } from 'react';
import { getUser, getTrees, getPlacedItems, getHabits } from './api';
import IsometricMap from './components/IsometricMap';
import HabitPanel from './components/HabitPanel';
import ShopPanel from './components/ShopPanel';
import InventoryPanel from './components/InventoryPanel';
import HabitForm from './components/HabitForm';
import ChatDashboard from './components/ChatDashboard';
import CalendarPanel from './components/CalendarPanel';
import RoutinePanel from './components/RoutinePanel';
import OllamaPopup from './components/OllamaPopup';
import TreeInfoModal from './components/TreeInfoModal';
import CharacterInfoModal from './components/CharacterInfoModal';
import Toast from './components/Toast';

export default function App() {
  const [user, setUser] = useState({ hearts: 0, level: 1, total_hearts_earned: 0 });
  const [trees, setTrees] = useState([]);
  const [placedItems, setPlacedItems] = useState([]);
  const [habits, setHabits] = useState([]);

  const [activePanel, setActivePanel] = useState(null); // 'habits' | 'shop' | 'inventory' | null
  const [showHabitForm, setShowHabitForm] = useState(false);
  const [toast, setToast] = useState(null);
  const [heartAnims, setHeartAnims] = useState([]);

  // 배치 모드: { ownedItemId, emoji, name } 또는 null
  const [placementMode, setPlacementMode] = useState(null);
  const [ollamaStatus, setOllamaStatus] = useState(null);
  const [showOllamaPopup, setShowOllamaPopup] = useState(false);

  // 씨앗 클릭 시 정보 모달
  const [selectedTree, setSelectedTree] = useState(null);
  // 배치된 캐릭터 클릭 시 정보 모달
  const [selectedChar, setSelectedChar] = useState(null);
  // 이동 모드 — { type: 'tree' | 'character', id, name, ... }
  const [moveMode, setMoveMode] = useState(null);

  const showToast = useCallback((msg) => {
    setToast(msg);
    setTimeout(() => setToast(null), 2500);
  }, []);

  const showHeartAnim = useCallback((x, y, amount) => {
    const id = Date.now();
    setHeartAnims((prev) => [...prev, { id, x, y, amount }]);
    setTimeout(() => setHeartAnims((prev) => prev.filter((a) => a.id !== id)), 1500);
  }, []);

  const refresh = useCallback(async () => {
    try {
      const [uRes, tRes, pRes, hRes] = await Promise.all([
        getUser(), getTrees(), getPlacedItems(), getHabits()
      ]);
      setUser(uRes.data);
      setTrees(tRes.data);
      setPlacedItems(pRes.data);
      setHabits(hRes.data);
    } catch (err) {
      console.error('데이터 로드 실패:', err);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  // Ollama 상태 확인 (앱 시작 시)
  const checkOllama = useCallback(async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/api/chat/health');
      const data = await res.json();
      setOllamaStatus(data);
      if (!data.ollama_installed || !data.ollama_running) {
        setShowOllamaPopup(true);
      }
    } catch {
      // 백엔드 미실행 시 무시
    }
  }, []);

  useEffect(() => { checkOllama(); }, [checkOllama]);

  const handleTreeClick = (tree) => {
    // 클릭 시 항상 정보 모달 표시 (수확은 모달 안에서)
    setSelectedTree(tree);
  };

  const handleTreeHarvested = (data) => {
    // TreeInfoModal 에서 수확 성공 시 호출됨
    showHeartAnim(window.innerWidth / 2, window.innerHeight / 2 - 50, data.harvested);
    refresh();
  };

  return (
    <>
      {/* 상단 바 */}
      <div className="top-bar">
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <div className="heart-display">
            <span className="heart-icon">&#10084;</span>
            <span className="heart-count">{user.hearts}</span>
          </div>
          <span className="level-badge">Lv.{user.level}</span>
        </div>
        <div className="top-buttons">
          <button
            className={`icon-btn ${activePanel === 'routine' ? 'icon-btn-active' : ''}`}
            onClick={() => setActivePanel(activePanel === 'routine' ? null : 'routine')}
            title="달성률"
          >📊</button>
          <button className="icon-btn" onClick={() => setActivePanel(activePanel === 'inventory' ? null : 'inventory')} title="인벤토리">&#128230;</button>
          <button className="icon-btn" onClick={() => setShowHabitForm(true)} title="일정 추가">&#43;</button>
        </div>
      </div>

      {/* 아이소메트릭 맵 */}
      <IsometricMap
        trees={trees}
        placedItems={placedItems}
        onTreeClick={handleTreeClick}
        onCharClick={(item) => { if (!moveMode) setSelectedChar(item); }}
        placementMode={placementMode}
        onSetPlacementMode={setPlacementMode}
        moveMode={moveMode}
        onSetMoveMode={setMoveMode}
        onRefresh={refresh}
        showToast={showToast}
      />

      {/* 하단 네비게이션 */}
      <div className="bottom-nav">
        <button
          className={`nav-btn ${activePanel === 'chat' ? 'active' : ''}`}
          onClick={() => setActivePanel(activePanel === 'chat' ? null : 'chat')}
        >
          🤖 채팅
        </button>
        <button
          className={`nav-btn ${activePanel === 'calendar' ? 'active' : ''}`}
          onClick={() => setActivePanel(activePanel === 'calendar' ? null : 'calendar')}
        >
          📅 캘린더
        </button>
        <button
          className={`nav-btn ${activePanel === 'habits' ? 'active' : ''}`}
          onClick={() => setActivePanel(activePanel === 'habits' ? null : 'habits')}
        >
          &#127793; 일정
        </button>
        <button
          className={`nav-btn ${activePanel === 'shop' ? 'active' : ''}`}
          onClick={() => setActivePanel(activePanel === 'shop' ? null : 'shop')}
        >
          &#128722; 상점
        </button>
        <button
          className={`nav-btn ${activePanel === 'inventory' ? 'active' : ''}`}
          onClick={() => setActivePanel(activePanel === 'inventory' ? null : 'inventory')}
        >
          &#128188; 배치
        </button>
      </div>

      {/* 패널 모달들 */}
      {activePanel === 'chat' && (
        <ChatDashboard onClose={() => setActivePanel(null)} />
      )}

      {activePanel === 'calendar' && (
        <CalendarPanel onClose={() => setActivePanel(null)} />
      )}

      {activePanel === 'habits' && (
        <HabitPanel
          habits={habits}
          onClose={() => setActivePanel(null)}
          onRefresh={refresh}
          showToast={showToast}
          showHeartAnim={showHeartAnim}
          onAddClick={() => setShowHabitForm(true)}
        />
      )}

      {activePanel === 'shop' && (
        <ShopPanel
          userHearts={user.hearts}
          userLevel={user.level}
          onClose={() => setActivePanel(null)}
          onRefresh={refresh}
          showToast={showToast}
        />
      )}

      {activePanel === 'inventory' && (
        <InventoryPanel
          onClose={() => setActivePanel(null)}
          onRefresh={refresh}
          showToast={showToast}
          onStartPlacement={(data) => {
            setPlacementMode(data);
            setActivePanel(null); // 모달 닫기
          }}
          placementMode={placementMode}
        />
      )}

      {activePanel === 'routine' && (
        <RoutinePanel
          habits={habits}
          onClose={() => setActivePanel(null)}
        />
      )}

      {/* 일정 추가 폼 */}
      {showHabitForm && (
        <HabitForm
          onClose={() => setShowHabitForm(false)}
          onRefresh={refresh}
          showToast={showToast}
        />
      )}

      {/* Ollama 미설치/미실행 팝업 */}
      {showOllamaPopup && ollamaStatus && (
        <OllamaPopup
          status={ollamaStatus}
          onClose={() => setShowOllamaPopup(false)}
          onRetry={() => { checkOllama(); }}
        />
      )}

      {/* 씨앗/나무 클릭 정보 모달 */}
      {selectedTree && (
        <TreeInfoModal
          tree={selectedTree}
          onClose={() => setSelectedTree(null)}
          onHarvested={handleTreeHarvested}
          onDeleted={() => { setSelectedTree(null); refresh(); }}
          onMove={(tree) => {
            setMoveMode({ type: 'tree', id: tree.id, name: tree.habit_title });
            setSelectedTree(null);
          }}
          showToast={showToast}
        />
      )}

      {/* 캐릭터 클릭 정보 모달 */}
      {selectedChar && (
        <CharacterInfoModal
          placedItem={selectedChar}
          onClose={() => setSelectedChar(null)}
          onMove={(item) => {
            setMoveMode({
              type: 'character',
              id: item.id,
              ownedItemId: item.owned_item_id,
              name: item.item_name,
              shopItemId: null,  // 이동은 owned_item_id 기준
            });
            setSelectedChar(null);
          }}
          onRemoved={refresh}
          showToast={showToast}
        />
      )}

      {/* 토스트 */}
      {toast && <Toast message={toast} />}

      {/* 하트 애니메이션 */}
      {heartAnims.map((a) => (
        <div
          key={a.id}
          className="heart-earn-anim"
          style={{ left: a.x, top: a.y }}
        >
          +{a.amount} &#10084;
        </div>
      ))}
    </>
  );
}
