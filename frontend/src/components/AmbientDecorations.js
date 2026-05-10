import React, { useMemo } from "react";

/**
 * 풀밭 위 무작위 데코 (꽃, 잡초, 버섯).
 * 비-상호작용. 그리드 셀 내부에 자유로운 위치 + 크기.
 *
 * 사용:
 *   <AmbientDecorations gridCols={5} gridRows={4} occupiedCells={[...]} />
 *   .iso-grid 의 직접 자식으로 들어가야 함 (grid 셀 차지).
 *
 * - useMemo 로 한 번만 계산, 재배열 없음.
 * - occupiedCells 에 트리/캐릭터 위치 넘기면 그 자리는 피함.
 */
const FLOWERS = [
  // 분홍 꽃
  (
    <g>
      <ellipse cx="0" cy="2" rx="6" ry="2" fill="#5e3a1e" opacity="0.3"/>
      <circle cx="-3" cy="-3" r="2.5" fill="#f8a8c4"/>
      <circle cx="3" cy="-3" r="2.5" fill="#f8a8c4"/>
      <circle cx="0" cy="-6" r="2.5" fill="#f8a8c4"/>
      <circle cx="-3" cy="0" r="2.5" fill="#f8a8c4"/>
      <circle cx="3" cy="0" r="2.5" fill="#f8a8c4"/>
      <circle cx="0" cy="-3" r="2" fill="#fff5cc"/>
    </g>
  ),
  // 노란 꽃
  (
    <g>
      <ellipse cx="0" cy="2" rx="5" ry="1.5" fill="#5e3a1e" opacity="0.3"/>
      <circle cx="-2" cy="-2" r="2" fill="#fde68a"/>
      <circle cx="2" cy="-2" r="2" fill="#fde68a"/>
      <circle cx="0" cy="-4" r="2" fill="#fde68a"/>
      <circle cx="0" cy="-2" r="1.5" fill="#f59e0b"/>
    </g>
  ),
  // 흰 꽃
  (
    <g>
      <ellipse cx="0" cy="2" rx="5" ry="1.5" fill="#5e3a1e" opacity="0.3"/>
      <circle cx="-2.5" cy="-2" r="2" fill="#ffffff"/>
      <circle cx="2.5" cy="-2" r="2" fill="#ffffff"/>
      <circle cx="0" cy="-4" r="2" fill="#ffffff"/>
      <circle cx="-2.5" cy="0" r="2" fill="#ffffff"/>
      <circle cx="2.5" cy="0" r="2" fill="#ffffff"/>
      <circle cx="0" cy="-2" r="1.5" fill="#fde68a"/>
    </g>
  ),
  // 잡초 (3가닥)
  (
    <g>
      <path d="M -4 4 Q -3 -4 -2 4" stroke="#3d6e2a" strokeWidth="1.2" fill="none"/>
      <path d="M 0 4 Q 1 -6 2 4" stroke="#3d6e2a" strokeWidth="1.2" fill="none"/>
      <path d="M 4 4 Q 3 -3 6 4" stroke="#3d6e2a" strokeWidth="1.2" fill="none"/>
    </g>
  ),
  // 작은 부쉬
  (
    <g>
      <ellipse cx="0" cy="3" rx="6" ry="2" fill="#5e3a1e" opacity="0.3"/>
      <circle cx="-3" cy="-1" r="3" fill="#5ea83b"/>
      <circle cx="3" cy="-1" r="3" fill="#6db84b"/>
      <circle cx="0" cy="-3" r="3" fill="#74c452"/>
    </g>
  ),
  // 빨간 버섯
  (
    <g>
      <ellipse cx="0" cy="3" rx="4" ry="1.5" fill="#5e3a1e" opacity="0.3"/>
      <rect x="-1.5" y="-1" width="3" height="4" fill="#f5e6d3"/>
      <ellipse cx="0" cy="-1" rx="5" ry="3" fill="#dc2626"/>
      <circle cx="-2" cy="-1.5" r="0.7" fill="white"/>
      <circle cx="2" cy="-2" r="0.6" fill="white"/>
    </g>
  ),
];


// 간단한 시드 PRNG (mulberry32)
function mulberry32(seed) {
  return function () {
    let t = (seed += 0x6D2B79F5);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}


export default function AmbientDecorations({
  gridCols = 5,
  gridRows = 4,
  density = 1.2,
  seed = 42,
  occupiedCells = [],
}) {
  const decorations = useMemo(() => {
    const rng = mulberry32(seed);
    const total = gridCols * gridRows;
    const num = Math.floor(total * density);

    const items = [];
    const occupiedSet = new Set(occupiedCells.map((c) => `${c.x},${c.y}`));

    for (let i = 0; i < num; i++) {
      const cellX = Math.floor(rng() * gridCols);
      const cellY = Math.floor(rng() * gridRows);
      const occupied = occupiedSet.has(`${cellX},${cellY}`);
      // 점유된 칸은 70% 확률로 스킵
      if (occupied && rng() > 0.3) continue;

      const offsetX = (rng() - 0.5) * 50;  // 셀 중앙 기준 ±25%
      const offsetY = (rng() - 0.5) * 50;
      const decoIdx = Math.floor(rng() * FLOWERS.length);
      const scale = 0.7 + rng() * 1.4;

      items.push({
        cellX, cellY, offsetX, offsetY,
        decoIdx, scale,
        key: `deco-${i}-${cellX}-${cellY}`,
      });
    }
    return items;
  }, [gridCols, gridRows, density, seed, occupiedCells]);

  return (
    <>
      {decorations.map((d) => (
        <div
          key={d.key}
          className="ambient-deco-cell"
          style={{
            gridColumn: d.cellX + 1,
            gridRow: d.cellY + 1,
            position: "relative",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            pointerEvents: "none",
            zIndex: 1,
          }}
        >
          <div
            className="ambient-deco-inner"
            style={{
              transform: `rotateZ(45deg) rotateX(-60deg) translate(${d.offsetX}%, ${d.offsetY}%) scale(${d.scale})`,
            }}
          >
            <svg viewBox="-15 -15 30 30" width="40" height="40" style={{ overflow: "visible" }}>
              {FLOWERS[d.decoIdx]}
            </svg>
          </div>
        </div>
      ))}
    </>
  );
}
