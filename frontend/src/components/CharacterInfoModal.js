import React from "react";
import { removePlacedItem, harvestPlacedItem } from "../api";
import "./TreeInfoModal.css";  // 같은 스타일 재활용

const RARITY_INTERVAL = {
  common:    "6시간마다 1하트",
  rare:      "4시간마다 2하트",
  unique:    "3시간마다 3하트",
  epic:      "2시간마다 4하트",
  legendary: "1시간마다 6하트",
};

const RARITY_KOR = {
  common: "일반",
  rare: "레어",
  unique: "유니크",
  epic: "에픽",
  legendary: "전설",
};

export default function CharacterInfoModal({ placedItem, onClose, onMove, onRemoved, onHarvested, showToast }) {
  if (!placedItem) return null;

  const isPixel = /pixel|픽셀/i.test(placedItem.item_image_url || "");
  const imgSrc = placedItem.item_image_url
    ? `/images/characters/${placedItem.item_image_url}`
    : null;

  const rarity = placedItem.rarity || "common";
  const pending = placedItem.pending_hearts || 0;
  const intervalDesc = RARITY_INTERVAL[rarity] || "—";
  const rarityKor = RARITY_KOR[rarity] || rarity;

  const handleMove = () => { onMove && onMove(placedItem); onClose(); };

  const handleHarvest = async () => {
    try {
      const res = await harvestPlacedItem(placedItem.id);
      showToast(res.data.message);
      onHarvested && onHarvested(res.data);
      onClose();
    } catch (err) {
      showToast(err.response?.data?.detail || "수확 실패");
    }
  };

  const handleRemove = async () => {
    try {
      await removePlacedItem(placedItem.id);
      showToast(`📦 '${placedItem.item_name}' 회수`);
      onRemoved && onRemoved();
      onClose();
    } catch (err) {
      showToast(err.response?.data?.detail || "회수 실패");
    }
  };

  return (
    <div className="tree-modal-backdrop" onClick={onClose}>
      <div className="tree-modal" onClick={(e) => e.stopPropagation()}>
        <button className="tree-modal-close" onClick={onClose}>✕</button>

        <div className="tree-modal-header">
          <div className="tree-modal-title">
            {placedItem.item_name}
            <span className={`rarity-badge rarity-${rarity}`} style={{ marginLeft: 8, position: 'static', display: 'inline-block' }}>
              {rarityKor}
            </span>
          </div>
          <div className="tree-modal-stage">타일 ({placedItem.grid_x}, {placedItem.grid_y})</div>
        </div>

        {/* 캐릭터 미리보기 */}
        <div style={{
          display: 'flex',
          justifyContent: 'center',
          padding: '16px 0',
          background: 'linear-gradient(180deg, #d8efc8 0%, #b9dfa1 100%)',
          borderRadius: '12px',
          margin: '4px 0 12px',
        }}>
          {imgSrc ? (
            <img src={imgSrc} alt={placedItem.item_name}
              style={{
                maxWidth: '140px', maxHeight: '160px', objectFit: 'contain',
                imageRendering: isPixel ? 'pixelated' : 'auto',
                filter: 'drop-shadow(0 4px 6px rgba(0,0,0,0.2))',
              }}
            />
          ) : <span style={{ fontSize: '60px' }}>{placedItem.item_emoji}</span>}
        </div>

        {/* 하트 생성 정보 */}
        <div className="tree-modal-next" style={{ background: 'linear-gradient(135deg, #ffe4e4, #ffb8b8)', borderColor: '#e8a8a8' }}>
          <div className="tree-modal-next-label">💗 시간당 하트</div>
          <div className="tree-modal-next-when">{intervalDesc}</div>
          {pending > 0 ? (
            <div className="tree-modal-next-remain" style={{ color: '#c0392b' }}>
              지금 수확 가능: ❤️ {pending}개
            </div>
          ) : (
            <div className="tree-modal-next-remain" style={{ color: '#8B6B47' }}>
              아직 누적된 하트 없음 (기다리세요)
            </div>
          )}
        </div>

        {/* 액션 버튼들 */}
        {pending > 0 && (
          <button className="tree-modal-harvest" onClick={handleHarvest}>
            ❤️ 하트 {pending}개 수확하기
          </button>
        )}

        <button
          onClick={handleMove}
          style={{
            width: '100%', padding: '11px',
            background: 'linear-gradient(135deg, #ffd166, #f5b942)',
            color: '#5D3A1A', border: 'none', borderRadius: '11px',
            fontSize: '14px', fontWeight: 700, cursor: 'pointer',
            marginTop: '8px',
            boxShadow: '0 3px 8px rgba(245, 185, 66, 0.3)',
          }}
        >
          🔄 다른 칸으로 이동
        </button>

        <button
          onClick={handleRemove}
          className="tree-modal-delete"
        >
          📦 인벤토리로 회수
        </button>
      </div>
    </div>
  );
}
