import React, { useState, useRef } from 'react';
import { removePlacedItem } from '../api';

export default function PlacementArea({
  placedItems,
  onPlaceItem,
  onRemoveItem,
  ownedItems,
  showToast,
}) {
  const [draggedItem, setDraggedItem] = useState(null);
  const [positions, setPositions] = useState(
    placedItems.reduce((acc, item) => {
      acc[item.id] = { x: item.grid_x * 80, y: item.grid_y * 80 };
      return acc;
    }, {})
  );
  const containerRef = useRef(null);

  const handleDragStart = (e, item) => {
    setDraggedItem(item);
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  };

  const handleDropOnArea = (e) => {
    e.preventDefault();
    if (!containerRef.current) return;

    const rect = containerRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    if (draggedItem && draggedItem.owned_item_id) {
      // 기존 배치 아이템 이동
      const newPos = { x: Math.max(0, x - 24), y: Math.max(0, y - 24) };
      setPositions((prev) => ({ ...prev, [draggedItem.id]: newPos }));
      showToast('아이템 위치 변경!');
    } else if (draggedItem && draggedItem.id && draggedItem.emoji) {
      // 인벤토리에서 새로 배치
      const newPos = { x: Math.max(0, x - 24), y: Math.max(0, y - 24) };
      const gridX = Math.round(newPos.x / 80);
      const gridY = Math.round(newPos.y / 80);
      onPlaceItem({
        owned_item_id: draggedItem.id, // shop_item_id 사용
        grid_x: gridX,
        grid_y: gridY,
      });
    }
    setDraggedItem(null);
  };

  const handleRemove = (itemId) => {
    onRemoveItem(itemId);
  };

  return (
    <div style={{ padding: '12px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {/* 인벤토리 (드래그 가능) */}
      <div>
        <div style={{ fontSize: '13px', fontWeight: '600', color: '#8B6914', marginBottom: '8px' }}>
          📦 내 아이템 (드래그해서 배치)
        </div>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(6, 1fr)',
            gap: '8px',
            maxHeight: '100px',
            overflowY: 'auto',
            padding: '8px',
            background: '#FFF8F0',
            borderRadius: '10px',
          }}
        >
          {ownedItems.map((item) => (
            <div
              key={item.id}
              draggable
              onDragStart={(e) => handleDragStart(e, item)}
              style={{
                background: 'white',
                borderRadius: '8px',
                padding: '8px',
                textAlign: 'center',
                cursor: 'grab',
                border: '1px solid #E8D5B8',
                transition: 'all 0.2s',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.1)')}
              onMouseLeave={(e) => (e.currentTarget.style.boxShadow = 'none')}
            >
              <span style={{ fontSize: '24px', display: 'block' }}>{item.emoji}</span>
              <div style={{ fontSize: '9px', color: '#8B6914', marginTop: '2px' }}>{item.name}</div>
            </div>
          ))}
        </div>
      </div>

      {/* 배치 영역 */}
      <div>
        <div style={{ fontSize: '13px', fontWeight: '600', color: '#8B6914', marginBottom: '8px' }}>
          🏞️ 배치 영역 (자유롭게 배치하세요)
        </div>
        <div
          ref={containerRef}
          onDragOver={handleDragOver}
          onDrop={handleDropOnArea}
          style={{
            width: '100%',
            height: '300px',
            background: 'linear-gradient(135deg, #F5E6D3 0%, #EAD7C0 100%)',
            borderRadius: '12px',
            border: '2px dashed #C4A882',
            position: 'relative',
            overflow: 'hidden',
            cursor: draggedItem ? 'grabbing' : 'default',
          }}
        >
          {/* 배치된 아이템들 */}
          {placedItems.map((item) => {
            const pos = positions[item.id] || { x: 0, y: 0 };
            return (
              <div
                key={item.id}
                draggable
                onDragStart={(e) => handleDragStart(e, item)}
                style={{
                  position: 'absolute',
                  left: pos.x,
                  top: pos.y,
                  width: '48px',
                  height: '48px',
                  background: 'white',
                  borderRadius: '8px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'grab',
                  fontSize: '32px',
                  border: '2px solid #5D8A5D',
                  boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
                  transition: draggedItem?.id === item.id ? 'none' : 'all 0.2s',
                  opacity: draggedItem?.id === item.id ? 0.8 : 1,
                }}
                onContextMenu={(e) => {
                  e.preventDefault();
                  handleRemove(item.id);
                }}
                title={`${item.item_name} (우클릭으로 제거)`}
              >
                {item.item_emoji}
              </div>
            );
          })}

          {placedItems.length === 0 && (
            <div
              style={{
                position: 'absolute',
                top: '50%',
                left: '50%',
                transform: 'translate(-50%, -50%)',
                textAlign: 'center',
                color: '#B8956A',
                fontSize: '14px',
              }}
            >
              위의 아이템을 드래그해서<br />여기에 배치하세요! 🎨
            </div>
          )}
        </div>

        <div style={{ fontSize: '11px', color: '#B8956A', marginTop: '6px' }}>
          💡 팁: 아이템을 드래그로 이동 | 우클릭으로 제거
        </div>
      </div>

      {/* 배치 통계 */}
      <div style={{ background: '#E8D5B8', borderRadius: '10px', padding: '10px', fontSize: '12px', color: '#5D3A1A' }}>
        🎨 배치 중: <strong>{placedItems.length}</strong>개 | 보유: <strong>{ownedItems.length}</strong>개
      </div>
    </div>
  );
}
