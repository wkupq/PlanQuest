import React from 'react';
import { placeItem, removePlacedItem } from '../api';

const TREE_EMOJIS = ['🌱', '🌿', '🌲', '🎄'];
const GRID_SIZE = 8; // 8x8 그리드 맵

export default function IsometricMap({
  trees,
  placedItems,
  onTreeClick,
  placementMode,
  onSetPlacementMode,
  onRefresh,
  showToast
}) {

  // 특정 타일 클릭 시 (아이템 배치 또는 하트 수확)
  const handleTileClick = async (x, y, treeItem) => {
    // 1. 배치 모드일 때: 클릭한 타일에 아이템 배치
    if (placementMode) {
      try {
        await placeItem({
          owned_item_id: placementMode.ownedItemId,
          grid_x: x,
          grid_y: y,
        });
        showToast(`✅ '${placementMode.name}' 배치 완료!`);
        onSetPlacementMode(null);
        onRefresh();
      } catch (err) {
        showToast(err.response?.data?.detail || '배치 실패');
      }
    } 
    // 2. 일반 모드일 때: 나무가 있으면 하트 수확
    else if (treeItem) {
      onTreeClick(treeItem);
    }
  };

  // 우클릭 시 아이템 제거
  const handleRemove = async (e, item) => {
    e.preventDefault();
    e.stopPropagation();
    try {
      await removePlacedItem(item.id);
      showToast('🗑️ 아이템 제거됨');
      onRefresh();
    } catch (err) {
      showToast('제거 실패');
    }
  };

  // 6x6 타일 생성
  const tiles = [];
  for (let y = 0; y < GRID_SIZE; y++) {
    for (let x = 0; x < GRID_SIZE; x++) {
      // 현재 x, y 좌표에 있는 배치된 아이템과 나무 찾기
      const placedItem = placedItems.find(i => i.grid_x === x && i.grid_y === y);
      const treeItem = trees.find(t => t.grid_x === x && t.grid_y === y);

      tiles.push(
        <div 
          key={`${x}-${y}`} 
          className="iso-tile"
          onClick={() => handleTileClick(x, y, treeItem)}
          onContextMenu={(e) => placedItem && handleRemove(e, placedItem)}
          title={
            placedItem ? `${placedItem.item_name}\n우클릭: 제거` : 
            treeItem ? treeItem.habit_title : ''
          }
        >
          {/* 타일 위에 세워질 이모지 및 UI */}
          <div className="iso-item">
            
            {/* 1. 상점에서 구매해 배치한 아이템 */}
            {placedItem && <span>{placedItem.item_emoji}</span>}
            
            {/* 2. 습관으로 심어진 나무 (배치된 아이템이 없을 때만 보임) */}
            {treeItem && !placedItem && (
              <>
                {/* 수확 가능한 하트 표시 */}
                {treeItem.hearts_available > 0 && (
                  <span className="item-heart" style={{ position: 'absolute', top: '-30px', fontSize: '18px' }}>
                    ❤️
                  </span>
                )}
                {/* 성장 단계에 따른 나무 이모지 */}
                <span>{TREE_EMOJIS[Math.min(treeItem.growth_stage, 3)]}</span>
              </>
            )}
            
          </div>
        </div>
      );
    }
  }

  return (
    <div className="iso-container">
      <div className="iso-grid">
        {tiles}
      </div>
      
      {/* 배치 모드 안내 */}
      {placementMode && (
        <div className="placement-guide" style={{
          position: 'absolute', 
          bottom: '20px', 
          background: 'white', 
          padding: '10px 20px', 
          borderRadius: '20px',
          boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
          display: 'flex',
          gap: '12px',
          alignItems: 'center',
          fontWeight: 'bold',
          color: '#5D3A1A'
        }}>
          🎯 {placementMode.emoji} {placementMode.name} 배치 중
          <button 
            className="placement-cancel" 
            onClick={() => onSetPlacementMode(null)}
            style={{
              background: '#e74c3c', color: 'white', border: 'none', 
              padding: '6px 12px', borderRadius: '8px', cursor: 'pointer'
            }}
          >
            ✕ 취소
          </button>
        </div>
      )}
    </div>
  );
}