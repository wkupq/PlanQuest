import React, { useRef, useState, useEffect } from 'react';
import { placeItem, removePlacedItem, moveTree } from '../api';
import TreeIcon from './TreeIcon';
import { computeNextAlarm } from '../utils/timeUtils';

// 배치도: 7x5 = 35 타일
const GRID_COLS = 7;
const GRID_ROWS = 5;
const TILE_SIZE = 160;
const SQRT1_2 = Math.SQRT1_2;  // 0.7071


// ─── 그리드 ↔ 화면 좌표 변환 ───────────────────────────
// rotateZ(-45) → rotateX(60) 의 결과를 직접 계산.
// (CSS 회전된 요소 hit-test 에 의존하지 않고 좌표를 정확히 매핑)

function gridToScreen(gx, gy) {
  const lx = (gx + 0.5 - GRID_COLS / 2) * TILE_SIZE;
  const ly = (gy + 0.5 - GRID_ROWS / 2) * TILE_SIZE;
  return {
    x: (lx + ly) * SQRT1_2,
    y: (ly - lx) * SQRT1_2 * 0.5,
  };
}

function screenToGrid(sx, sy) {
  // gridToScreen 의 역. (sx, sy) = 컨테이너 중심 기준 오프셋
  // sx = (lx + ly) * 0.707
  // sy = (ly - lx) * 0.354
  const lx_plus_ly = sx / SQRT1_2;            // = lx + ly
  const ly_minus_lx = sy / SQRT1_2 / 0.5;     // = ly - lx
  const lx = (lx_plus_ly - ly_minus_lx) / 2;
  const ly = (lx_plus_ly + ly_minus_lx) / 2;
  return {
    gx: Math.round(lx / TILE_SIZE + GRID_COLS / 2 - 0.5),
    gy: Math.round(ly / TILE_SIZE + GRID_ROWS / 2 - 0.5),
  };
}


const getImageSrc = (imageUrl) => {
  if (!imageUrl) return null;
  return `/images/characters/${imageUrl}`;
};


export default function IsometricMap({
  trees,
  placedItems,
  onTreeClick,
  onCharClick,
  placementMode,
  onSetPlacementMode,
  moveMode,
  onSetMoveMode,
  onRefresh,
  showToast
}) {
  const containerRef = useRef(null);
  const [hoverCell, setHoverCell] = useState(null);
  const [, setMinuteTick] = useState(0);  // 1분마다 강제 리렌더 (시간 배지 갱신용)

  useEffect(() => {
    const id = setInterval(() => setMinuteTick((t) => t + 1), 60_000);
    return () => clearInterval(id);
  }, []);

  // ─── 컨테이너 클릭 → 역산으로 grid 좌표 → 액션 ──
  const handleContainerClick = async (e) => {
    // 빌보드 (캐릭터/나무) 가 직접 잡은 클릭은 여기로 안 옴 (stopPropagation)
    if (e.target.closest('.billboard')) return;

    const rect = containerRef.current.getBoundingClientRect();
    const sx = e.clientX - rect.left - rect.width / 2;
    const sy = e.clientY - rect.top - rect.height / 2;
    const { gx, gy } = screenToGrid(sx, sy);

    if (gx < 0 || gx >= GRID_COLS || gy < 0 || gy >= GRID_ROWS) {
      // 그리드 밖 클릭 → 무시
      return;
    }

    if (placementMode) {
      try {
        await placeItem({
          owned_item_id: placementMode.ownedItemId,
          grid_x: gx,
          grid_y: gy,
        });
        showToast(`✅ '${placementMode.name}' 배치 완료!`);
        onSetPlacementMode(null);
        onRefresh();
      } catch (err) {
        showToast(err.response?.data?.detail || '배치 실패');
      }
      return;
    }

    if (moveMode) {
      try {
        if (moveMode.type === 'tree') {
          await moveTree(moveMode.id, gx, gy);
          showToast(`🔄 '${moveMode.name}' 이동 완료`);
        } else if (moveMode.type === 'character') {
          // 캐릭터 이동 = placeItem 재호출 (upsert: 기존 PlacedItem 의 grid 만 갱신)
          await placeItem({
            owned_item_id: moveMode.ownedItemId,
            grid_x: gx,
            grid_y: gy,
          });
          showToast(`🔄 '${moveMode.name}' 이동 완료`);
        }
        onSetMoveMode(null);
        onRefresh();
      } catch (err) {
        showToast(err.response?.data?.detail || '이동 실패');
      }
      return;
    }

    // 비-배치/이동 모드: 그 칸에 나무 있으면 모달 열기
    const tree = trees.find(t => t.grid_x === gx && t.grid_y === gy);
    if (tree) {
      onTreeClick(tree);
    }
  };

  const handleContainerMove = (e) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const sx = e.clientX - rect.left - rect.width / 2;
    const sy = e.clientY - rect.top - rect.height / 2;
    const { gx, gy } = screenToGrid(sx, sy);
    if (gx >= 0 && gx < GRID_COLS && gy >= 0 && gy < GRID_ROWS) {
      if (!hoverCell || hoverCell.gx !== gx || hoverCell.gy !== gy) {
        setHoverCell({ gx, gy });
      }
    } else if (hoverCell) {
      setHoverCell(null);
    }
  };

  const handleContainerLeave = () => setHoverCell(null);

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


  // ─── 1. 바닥 타일 (배경) — 클릭 X (컨테이너에서 처리) ───
  const tiles = [];
  for (let y = 0; y < GRID_ROWS; y++) {
    for (let x = 0; x < GRID_COLS; x++) {
      const isHover = hoverCell && hoverCell.gx === x && hoverCell.gy === y;
      tiles.push(
        <div
          key={`${x}-${y}`}
          className={
            'iso-tile'
            + ((placementMode || moveMode) ? ' tile-placeable' : '')
            + (isHover ? ' tile-hover' : '')
          }
        />
      );
    }
  }

  // ─── 2. 빌보드 레이어 (캐릭터/나무, 회전 X) ───
  const billboards = [];

  for (const tree of trees) {
    const placedHere = placedItems.find(p => p.grid_x === tree.grid_x && p.grid_y === tree.grid_y);
    if (placedHere) continue;

    const { x, y } = gridToScreen(tree.grid_x, tree.grid_y);
    const z = tree.grid_x + tree.grid_y;

    // 다음 알람까지 남은 시간 (분 단위 배지용)
    const nextAlarm = computeNextAlarm(tree.times || [], tree.repeat_days || []);
    // 24시간 이내 알람이면 시계 색상, 그 이상이면 회색 톤
    const badgeUrgent = nextAlarm && nextAlarm.minutesUntil <= 60;

    billboards.push(
      <div
        key={`tree-${tree.id}`}
        className="billboard"
        style={{ left: `calc(50% + ${x}px)`, top: `calc(50% + ${y}px)`, zIndex: 100 + z }}
        onClick={(e) => { e.stopPropagation(); onTreeClick(tree); }}
      >
        {/* 시간 배지 — 나무 위에 작게 (분 단위) */}
        {nextAlarm && (
          <span className={`time-badge${badgeUrgent ? ' time-badge-urgent' : ''}`}>
            ⏱ {nextAlarm.shortText}
          </span>
        )}
        {tree.hearts_available > 0 && <span className="item-heart">❤️</span>}
        <TreeIcon stage={tree.growth_stage} hasHarvest={tree.hearts_available > 0} />
        <div className="billboard-shadow" />
      </div>
    );
  }

  for (const item of placedItems) {
    const imgSrc = getImageSrc(item.item_image_url);
    const isPixel = /pixel|픽셀/i.test(item.item_image_url || '');
    const { x, y } = gridToScreen(item.grid_x, item.grid_y);
    const z = item.grid_x + item.grid_y;
    const isMoving = moveMode && moveMode.type === 'character' && moveMode.id === item.id;
    billboards.push(
      <div
        key={`char-${item.id}`}
        className={`billboard${isMoving ? ' billboard-moving' : ''}`}
        style={{ left: `calc(50% + ${x}px)`, top: `calc(50% + ${y}px)`, zIndex: 100 + z + 1 }}
        onClick={(e) => {
          e.stopPropagation();
          if (placementMode || moveMode) return;  // 모드 중에는 모달 X
          onCharClick && onCharClick(item);
        }}
        onContextMenu={(e) => handleRemove(e, item)}
        title={`${item.item_name}\n클릭: 메뉴 / 우클릭: 회수`}
      >
        {imgSrc ? (
          <img
            src={imgSrc}
            alt={item.item_name}
            className={`billboard-char${isPixel ? ' pixel-art' : ''}`}
            draggable={false}
            onError={(e) => { e.target.style.display = 'none'; e.target.nextSibling.style.display = 'block'; }}
          />
        ) : null}
        <span style={{ display: imgSrc ? 'none' : 'block', fontSize: '60px' }}>
          {item.item_emoji}
        </span>
        <div className="billboard-shadow" />
      </div>
    );
  }

  return (
    <div
      className="iso-container"
      ref={containerRef}
      onClick={handleContainerClick}
      onMouseMove={handleContainerMove}
      onMouseLeave={handleContainerLeave}
    >
      <div className="iso-grid">
        {tiles}
      </div>

      <div className="iso-billboards">
        {billboards}
      </div>

      {placementMode && (
        <ModeGuide
          icon="🎯"
          label={`${placementMode.emoji || ''} ${placementMode.name} 배치 중`}
          onCancel={() => onSetPlacementMode(null)}
        />
      )}
      {moveMode && (
        <ModeGuide
          icon="🔄"
          label={`'${moveMode.name}' 이동 중 — 빈 칸 클릭하세요`}
          onCancel={() => onSetMoveMode(null)}
          color="#f5b942"
        />
      )}
    </div>
  );
}


// 하단 가이드 박스 (배치/이동 모드 공통)
function ModeGuide({ icon, label, onCancel, color }) {
  return (
    <div style={{
      position: 'absolute',
      bottom: '20px',
      left: '50%',
      transform: 'translateX(-50%)',
      background: 'white',
      padding: '10px 20px',
      borderRadius: '20px',
      boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
      display: 'flex',
      gap: '12px',
      alignItems: 'center',
      fontWeight: 'bold',
      color: '#5D3A1A',
      borderLeft: color ? `4px solid ${color}` : undefined,
      zIndex: 1000,
    }}>
      {icon} {label}
      <button
        onClick={(e) => { e.stopPropagation(); onCancel(); }}
        style={{
          background: '#e74c3c', color: 'white', border: 'none',
          padding: '6px 12px', borderRadius: '8px', cursor: 'pointer',
          fontWeight: 'bold',
        }}
      >
        ✕ 취소
      </button>
    </div>
  );
}
