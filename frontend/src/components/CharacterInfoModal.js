import React from "react";
import { removePlacedItem } from "../api";
import "./TreeInfoModal.css";  // 같은 스타일 재활용

/**
 * 배치된 캐릭터 클릭 시 액션 팝업.
 *
 * Props:
 *   placedItem  : { id, item_name, item_image_url, item_emoji, grid_x, grid_y }
 *   onClose     : 닫기
 *   onMove      : 이동 모드 시작 (App.js 가 moveMode 상태 설정)
 *   onRemoved   : 회수 (제거) 성공 시
 *   showToast   : 토스트
 */
export default function CharacterInfoModal({ placedItem, onClose, onMove, onRemoved, showToast }) {
  if (!placedItem) return null;

  const isPixel = /pixel|픽셀/i.test(placedItem.item_image_url || "");
  const imgSrc = placedItem.item_image_url
    ? `/images/characters/${placedItem.item_image_url}`
    : null;

  const handleMove = () => {
    onMove && onMove(placedItem);
    onClose();
  };

  const handleRemove = async () => {
    try {
      await removePlacedItem(placedItem.id);
      showToast(`📦 '${placedItem.item_name}' 회수 (인벤토리로)`);
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
          <div className="tree-modal-title">{placedItem.item_name}</div>
          <div className="tree-modal-stage">
            타일 ({placedItem.grid_x}, {placedItem.grid_y})
          </div>
        </div>

        {/* 캐릭터 이미지 미리보기 */}
        <div style={{
          display: 'flex',
          justifyContent: 'center',
          padding: '16px 0',
          background: 'linear-gradient(180deg, #d8efc8 0%, #b9dfa1 100%)',
          borderRadius: '12px',
          margin: '4px 0 16px',
        }}>
          {imgSrc ? (
            <img
              src={imgSrc}
              alt={placedItem.item_name}
              style={{
                maxWidth: '120px',
                maxHeight: '140px',
                objectFit: 'contain',
                imageRendering: isPixel ? 'pixelated' : 'auto',
                filter: 'drop-shadow(0 4px 6px rgba(0,0,0,0.2))',
              }}
            />
          ) : (
            <span style={{ fontSize: '60px' }}>{placedItem.item_emoji}</span>
          )}
        </div>

        {/* 액션 버튼 — 이동 / 회수 */}
        <button
          onClick={handleMove}
          style={{
            width: '100%',
            padding: '12px',
            background: 'linear-gradient(135deg, #ffd166, #f5b942)',
            color: '#5D3A1A',
            border: 'none',
            borderRadius: '12px',
            fontSize: '15px',
            fontWeight: 700,
            cursor: 'pointer',
            marginBottom: '8px',
            boxShadow: '0 3px 10px rgba(245, 185, 66, 0.35)',
            transition: 'transform 0.1s',
          }}
          onMouseDown={(e) => e.currentTarget.style.transform = 'translateY(1px)'}
          onMouseUp={(e) => e.currentTarget.style.transform = ''}
        >
          🔄 다른 칸으로 이동하기
        </button>

        <button
          onClick={handleRemove}
          style={{
            width: '100%',
            padding: '10px',
            background: 'transparent',
            color: '#8B4513',
            border: '1px solid #d4b896',
            borderRadius: '10px',
            fontSize: '13px',
            fontWeight: 500,
            cursor: 'pointer',
          }}
        >
          📦 정원에서 빼기 (인벤토리로 회수)
        </button>

        <div style={{
          marginTop: '10px',
          fontSize: '11px',
          color: '#8B6B47',
          textAlign: 'center',
        }}>
          회수해도 캐릭터는 인벤토리에 남아 있어요. 다시 배치할 수 있습니다.
        </div>
      </div>
    </div>
  );
}
