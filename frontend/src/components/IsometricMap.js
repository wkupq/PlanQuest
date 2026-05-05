import React from 'react';
import { placeItem, removePlacedItem } from '../api';

const TREE_EMOJIS = ['🌱', '🌿', '🌲', '🎄'];
const GRID_SIZE = 8;

const getImageSrc = (imageUrl) => {
  if (!imageUrl) return null;
  return `/images/characters/${imageUrl}`;
};

export default function IsometricMap({
  trees,
  placedItems,
  onTreeClick,
  placementMode,
  onSetPlacementMode,
  onRefresh,
  showToast
}) {

  const handleTileClick = async (x, y, treeItem) => {
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
    } else if (treeItem) {
      onTreeClick(treeItem);
    }
  };

  const handleRemove = async (e, item) => {
    e.preventDefault();
    e.stopPropagation();
    try {
      await removePlacedItem(item.id);
      showToast('🗑️ 캐릭터 제거됨');
      onRefresh();
    } catch (err) {
      showToast('제거 실패');
    }
  };

  const tiles = [];
  for (let y = 0; y < GRID_SIZE; y++) {
    for (let x = 0; x < GRID_SIZE; x++) {
      const placedItem = placedItems.find(i => i.grid_x === x && i.grid_y === y);
      const treeItem = trees.find(t => t.grid_x === x && t.grid_y === y);
      const imgSrc = placedItem ? getImageSrc(placedItem.item_image_url) : null;

      tiles.push(
        <div
          key={`${x}-${y}`}
          className={`iso-tile ${placementMode ? 'tile-placeable' : ''}`}
          onClick={() => handleTileClick(x, y, treeItem)}
          onContextMenu={(e) => placedItem && handleRemove(e, placedItem)}
          title={
            placedItem ? `${placedItem.item_name}\n우클릭: 제거` :
            treeItem ? treeItem.habit_title : ''
          }
        >
          {/* 캐릭터/아이템 영역 - 타일 위에 3D로 서있음 */}
          <div className="iso-item">

            {/* 1. 배치된 캐릭터 (이미지 또는 이모지) */}
            {placedItem && (
              <div className="character-on-tile">
                {imgSrc ? (
                  <img
                    src={imgSrc}
                    alt={placedItem.item_name}
                    className="char-img-on-tile"
                    onError={(e) => { e.target.style.display = 'none'; e.target.nextSibling.style.display = 'block'; }}
                  />
                ) : null}
                <span style={{ display: imgSrc ? 'none' : 'block', fontSize: '52px' }}>
                  {placedItem.item_emoji}
                </span>
                {/* 캐릭터 그림자 */}
                <div className="char-shadow"></div>
              </div>
            )}

            {/* 2. 일정으로 심어진 나무 */}
            {treeItem && !placedItem && (
              <>
                {treeItem.hearts_available > 0 && (
                  <span className="item-heart" style={{ position: 'absolute', top: '-30px', fontSize: '18px' }}>
                    ❤️
                  </span>
                )}
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
