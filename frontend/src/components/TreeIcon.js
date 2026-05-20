import React from "react";

/**
 * 씨앗 → 새싹 → 어린나무 → 큰나무 (4단계).
 *
 * stage 1 (새싹) 은 사용자 PNG 사용.
 * stage 0/2/3 은 같은 색상 팔레트 + 일러스트 톤으로 SVG.
 *
 * 색상 팔레트 (사용자 PNG 에서 추출):
 *   잎 (앞):    #7F9B56  (sage green)
 *   잎 (뒷):    #6B8246  (좀 더 어두움)
 *   잎 vein:   #A06A3A  (reddish brown 중심선)
 *   줄기:      #AC845B  (warm brown)
 *   줄기 음영:  #8B6740
 *   흙:       #6B5440
 *   열매:      #C7493B  (큰나무용 빨간 열매)
 */

const PNG_PATH = (stage) => `/images/seeds/seed_stage_${stage}.png`;

// ─── SVG 폴백 (PNG 없을 때) — 같은 컬러 팔레트 ───────
const SVG_STAGES = [
  // 0: 씨앗 (도토리, 흙에 박힘) ─────────────────────
  (
    <svg key="0" viewBox="0 0 100 140" xmlns="http://www.w3.org/2000/svg">
      {/* 흙 더미 */}
      <ellipse cx="50" cy="128" rx="36" ry="6" fill="#6B5440" opacity="0.85"/>
      <ellipse cx="50" cy="124" rx="30" ry="3" fill="#8B6740" opacity="0.6"/>

      {/* 도토리 본체 (아래쪽 통통한 부분) */}
      <ellipse cx="50" cy="108" rx="16" ry="20" fill="#AC845B"/>
      {/* 도토리 음영 */}
      <ellipse cx="44" cy="108" rx="6" ry="14" fill="#8B6740" opacity="0.5"/>

      {/* 도토리 모자 (위쪽 짙은 갈색) */}
      <path d="M 32 92 Q 50 78 68 92 L 68 100 Q 50 90 32 100 Z"
            fill="#6B5440"/>
      <path d="M 32 92 Q 50 78 68 92" fill="none" stroke="#5a4530" strokeWidth="0.8"/>

      {/* 모자 꼭지 줄기 */}
      <path d="M 50 78 L 50 70" stroke="#6B5440" strokeWidth="2.5" strokeLinecap="round"/>

      {/* 모자 무늬 (점들) */}
      <circle cx="42" cy="92" r="0.8" fill="#3d2614" opacity="0.5"/>
      <circle cx="58" cy="91" r="0.8" fill="#3d2614" opacity="0.5"/>
      <circle cx="50" cy="95" r="0.8" fill="#3d2614" opacity="0.5"/>
    </svg>
  ),

  // 1: 새싹 — PNG 우선 사용 (stage_1.png), 폴백 SVG 도 일관된 스타일 ──
  (
    <svg key="1" viewBox="0 0 100 140" xmlns="http://www.w3.org/2000/svg">
      <ellipse cx="50" cy="132" rx="34" ry="5" fill="#6B5440" opacity="0.7"/>

      {/* 줄기 */}
      <path d="M 50 130 Q 49 95 50 80" stroke="#AC845B" strokeWidth="3.5"
            fill="none" strokeLinecap="round"/>

      {/* 왼쪽 잎 */}
      <ellipse cx="36" cy="78" rx="14" ry="8.5" fill="#7F9B56"
               transform="rotate(-30 36 78)"/>
      <path d="M 26 84 Q 36 76 46 74" fill="none" stroke="#A06A3A"
            strokeWidth="1.4" strokeLinecap="round"
            transform="rotate(-30 36 78)"/>

      {/* 오른쪽 잎 */}
      <ellipse cx="64" cy="72" rx="14" ry="8.5" fill="#7F9B56"
               transform="rotate(30 64 72)"/>
      <path d="M 54 78 Q 64 70 74 68" fill="none" stroke="#A06A3A"
            strokeWidth="1.4" strokeLinecap="round"
            transform="rotate(30 64 72)"/>
    </svg>
  ),

  // 2: 어린 나무 — 줄기 더 굵고 잎 4장 ─────────────
  (
    <svg key="2" viewBox="0 0 100 140" xmlns="http://www.w3.org/2000/svg">
      {/* 흙 */}
      <ellipse cx="50" cy="132" rx="38" ry="6" fill="#6B5440" opacity="0.85"/>

      {/* 줄기 (살짝 굵게, 약간 곡선) */}
      <path d="M 50 130 Q 48 95 50 70" stroke="#AC845B" strokeWidth="5"
            fill="none" strokeLinecap="round"/>
      {/* 줄기 음영 */}
      <path d="M 51 128 Q 50 96 51 72" stroke="#8B6740" strokeWidth="1.8"
            fill="none" strokeLinecap="round" opacity="0.7"/>

      {/* 잎 4장 — 줄기 양옆 위아래 */}
      {/* 왼쪽 위 잎 */}
      <ellipse cx="32" cy="62" rx="15" ry="9" fill="#7F9B56"
               transform="rotate(-35 32 62)"/>
      <path d="M 22 68 Q 32 60 42 58" fill="none" stroke="#A06A3A"
            strokeWidth="1.4" strokeLinecap="round"
            transform="rotate(-35 32 62)"/>

      {/* 오른쪽 위 잎 */}
      <ellipse cx="68" cy="56" rx="15" ry="9" fill="#7F9B56"
               transform="rotate(35 68 56)"/>
      <path d="M 58 62 Q 68 54 78 52" fill="none" stroke="#A06A3A"
            strokeWidth="1.4" strokeLinecap="round"
            transform="rotate(35 68 56)"/>

      {/* 왼쪽 아래 잎 (살짝 어둡게 - 뒤쪽 느낌) */}
      <ellipse cx="34" cy="92" rx="13" ry="7.5" fill="#6B8246"
               transform="rotate(-20 34 92)"/>
      <path d="M 25 96 Q 34 90 43 88" fill="none" stroke="#A06A3A"
            strokeWidth="1.2" strokeLinecap="round"
            transform="rotate(-20 34 92)"/>

      {/* 오른쪽 아래 잎 */}
      <ellipse cx="66" cy="88" rx="13" ry="7.5" fill="#6B8246"
               transform="rotate(20 66 88)"/>
      <path d="M 57 92 Q 66 86 75 84" fill="none" stroke="#A06A3A"
            strokeWidth="1.2" strokeLinecap="round"
            transform="rotate(20 66 88)"/>

      {/* 꼭대기 작은 새 잎 */}
      <ellipse cx="50" cy="50" rx="8" ry="5" fill="#7F9B56"/>
      <path d="M 44 51 Q 50 49 56 51" fill="none" stroke="#A06A3A"
            strokeWidth="1" strokeLinecap="round"/>
    </svg>
  ),

  // 3: 큰 나무 — 굵은 갈색 줄기 + 풍성한 잎 무리 + 빨간 열매 ──
  (
    <svg key="3" viewBox="0 0 100 140" xmlns="http://www.w3.org/2000/svg">
      {/* 흙 */}
      <ellipse cx="50" cy="134" rx="42" ry="7" fill="#6B5440" opacity="0.9"/>

      {/* 굵은 나무 줄기 (사다리꼴) */}
      <path d="M 42 134 L 44 70 L 56 70 L 58 134 Z" fill="#AC845B"/>
      {/* 줄기 텍스처 (음영 라인) */}
      <line x1="46" y1="80" x2="46" y2="128" stroke="#8B6740" strokeWidth="1" opacity="0.7"/>
      <line x1="50" y1="76" x2="50" y2="132" stroke="#8B6740" strokeWidth="0.6" opacity="0.4"/>
      <line x1="54" y1="82" x2="54" y2="130" stroke="#8B6740" strokeWidth="0.8" opacity="0.5"/>

      {/* 가지 (양옆으로 살짝 뻗음) */}
      <path d="M 47 75 Q 38 60 32 50" stroke="#AC845B" strokeWidth="3"
            fill="none" strokeLinecap="round"/>
      <path d="M 53 75 Q 62 58 68 48" stroke="#AC845B" strokeWidth="3"
            fill="none" strokeLinecap="round"/>

      {/* 잎 무리 — 여러 개 겹쳐서 풍성하게 */}
      {/* 뒤쪽 (어두운) 잎 큰 무리 */}
      <ellipse cx="50" cy="48" rx="32" ry="22" fill="#6B8246"/>

      {/* 중간 잎 무리 */}
      <ellipse cx="34" cy="50" rx="16" ry="11" fill="#7F9B56"
               transform="rotate(-15 34 50)"/>
      <ellipse cx="66" cy="46" rx="16" ry="11" fill="#7F9B56"
               transform="rotate(15 66 46)"/>
      <ellipse cx="50" cy="38" rx="14" ry="10" fill="#7F9B56"/>

      {/* 앞쪽 작은 잎 (포인트) */}
      <ellipse cx="42" cy="60" rx="10" ry="6" fill="#7F9B56"
               transform="rotate(-25 42 60)"/>
      <path d="M 32 62 Q 42 58 52 58" fill="none" stroke="#A06A3A"
            strokeWidth="1.2" strokeLinecap="round"
            transform="rotate(-25 42 60)"/>
      <ellipse cx="58" cy="58" rx="10" ry="6" fill="#7F9B56"
               transform="rotate(25 58 58)"/>
      <path d="M 48 60 Q 58 56 68 56" fill="none" stroke="#A06A3A"
            strokeWidth="1.2" strokeLinecap="round"
            transform="rotate(25 58 58)"/>

      {/* 빨간 열매 (수확 가능 신호) */}
      <circle cx="36" cy="54" r="3.5" fill="#C7493B"/>
      <circle cx="35" cy="53" r="1" fill="#fff" opacity="0.6"/>
      <circle cx="64" cy="50" r="3.5" fill="#C7493B"/>
      <circle cx="63" cy="49" r="1" fill="#fff" opacity="0.6"/>
      <circle cx="50" cy="62" r="3.5" fill="#C7493B"/>
      <circle cx="49" cy="61" r="1" fill="#fff" opacity="0.6"/>
    </svg>
  ),
];


/**
 * @param {number} stage  - 0~3 (성장 단계).
 * @param {boolean} hasHarvest - 수확 가능 시 살짝 반짝임.
 */
export default function TreeIcon({ stage = 0, hasHarvest = false }) {
  const s = Math.max(0, Math.min(3, stage));
  const [usePNG, setUsePNG] = React.useState(true);

  return (
    <div className={`tree-icon ${hasHarvest ? "tree-pulse" : ""}`}>
      {usePNG ? (
        <img
          src={PNG_PATH(s)}
          alt={`tree-stage-${s}`}
          onError={() => setUsePNG(false)}
          style={{ width: "100%", height: "100%", objectFit: "contain", objectPosition: "center bottom" }}
        />
      ) : (
        SVG_STAGES[s]
      )}
    </div>
  );
}
