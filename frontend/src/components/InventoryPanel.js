import React, { useState, useEffect } from 'react';
import { getShopItems, getPlacedItems } from '../api';

export default function InventoryPanel({ onClose, onRefresh, showToast, onStartPlacement, placementMode }) {
  const [ownedItems, setOwnedItems] = useState([]);
  const [placedItemsList, setPlacedItemsList] = useState([]);

  const loadData = async () => {
    try {
      const [shopRes, placedRes] = await Promise.all([
        getShopItems(),
        getPlacedItems()
      ]);
      const owned = shopRes.data.filter(i => i.owned);
      setOwnedItems(owned);
      setPlacedItemsList(placedRes.data);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => { loadData(); }, []);

  const handleItemClick = (item) => {
    // 배치 모드 시작 - 모달은 자동으로 닫힘
    onStartPlacement({
      ownedItemId: item.id,
      emoji: item.emoji,
      name: item.name
    });
    showToast(`${item.name}을 배치할 위치를 선택하세요! 🖱️`);
  };

  const placedOwnerIds = new Set(placedItemsList.map(p => p.owned_item_id));

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-title">&#128188; 내 아이템</div>

        {ownedItems.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '20px', color: '#B8956A' }}>
            아직 아이템이 없어요.<br />상점에서 구매해보세요!
          </div>
        ) : (
          <>
            <div style={{ fontSize: '13px', color: '#8B6914', marginBottom: '12px' }}>
              📍 배치할 아이템을 클릭하세요
            </div>
            <div className="inventory-grid">
              {ownedItems.map((item) => {
                const isPlaced = placedOwnerIds.has(item.id);
                const isSelecting = placementMode?.ownedItemId === item.id;

                return (
                  <div
                    key={item.id}
                    className="inventory-item"
                    onClick={() => handleItemClick(item)}
                    style={{
                      cursor: 'pointer',
                      borderColor: isSelecting ? '#FFD700' : (isPlaced ? '#5D8A5D' : undefined),
                      borderWidth: isSelecting ? '3px' : undefined,
                      backgroundColor: isSelecting ? '#FFFACD' : undefined,
                      transform: isSelecting ? 'scale(1.05)' : undefined,
                      transition: 'all 0.2s ease'
                    }}
                    title={isPlaced ? '이미 배치됨' : '클릭해서 배치'}
                  >
                    <span className="emoji">{item.emoji}</span>
                    <div className="name">{item.name}</div>
                  </div>
                );
              })}
            </div>
          </>
        )}

        {placedItemsList.length > 0 && (
          <>
            <div style={{ fontSize: '13px', color: '#8B6914', marginTop: '16px', marginBottom: '8px' }}>
              ✅ 배치된 아이템 ({placedItemsList.length}개)
            </div>
            <div className="inventory-grid">
              {placedItemsList.map((p) => (
                <div
                  key={p.id}
                  className="inventory-item"
                  style={{
                    borderColor: '#5D8A5D',
                    opacity: 0.8
                  }}
                  title="배치된 아이템"
                >
                  <span className="emoji">{p.item_emoji}</span>
                  <div className="name">{p.item_name}</div>
                </div>
              ))}
            </div>
          </>
        )}

        {placementMode && (
          <div style={{
            marginTop: '16px',
            padding: '12px',
            backgroundColor: '#FFF8DC',
            border: '2px solid #FFD700',
            borderRadius: '8px',
            textAlign: 'center',
            color: '#8B6914',
            fontWeight: 'bold'
          }}>
            🎯 배치 모드 활성화: {placementMode.name} {placementMode.emoji}
            <br />
            <span style={{ fontSize: '12px', color: '#B8956A', marginTop: '4px', display: 'block' }}>
              지도에서 원하는 위치를 클릭하세요
            </span>
          </div>
        )}

        <button
          className="cancel-btn"
          onClick={onClose}
          style={{ marginTop: '16px' }}
        >
          닫기
        </button>
      </div>
    </div>
  );
}
