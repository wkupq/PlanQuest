import React, { useRef, useState, useEffect } from 'react';
import { placeItem, removePlacedItem, moveTree, movePlacedItem } from '../api';
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
          // PlacedItem.id 기준으로 정확하게 이동 (버그 수정)
          await movePlacedItem(moveMode.id, gx, gy);
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
    cons