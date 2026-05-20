# 🎉 Week 5 완료 — Team Member D

**완료일:** 2026-05-11
**범위:** Week 5 (D 역할 자체 기획 — 원래 로드맵엔 없던 추가 5주차)
**테마:** AI 인사이트 + 메모리 자동화 + 실시간 푸시

W4 까지의 기반(메모리, 게임 상태 도구, 능동 추천) 위에 **사용자 경험 향상** 레이어 추가.

---

## 📂 W5 추가/변경 파일

```
backend/
├── routers/
│   ├── insights.py        ★ NEW — AI 주간/월간 리포트 + 추천
│   └── notifications.py   ★ NEW — WebSocket 실시간 알림
├── memory_engine.py       (수정) — auto_categorize, auto_importance 추가
├── routers/memory.py      (수정) — /auto-add, /recategorize 엔드포인트
├── main.py                (수정) — insights, notifications 라우터 등록
└── test_d_features.py     (수정) — W5 항목 3개 추가
```

---

## 🆕 새 API 엔드포인트

### AI 인사이트 리포트
```
GET  /api/insights/weekly?use_llm=true   — 지난 7일 LLM 자연어 분석
GET  /api/insights/monthly?use_llm=true  — 지난 30일 분석
GET  /api/insights/quick                 — LLM 없이 즉시 한 줄 요약
```

응답 예:
```json
{
  "period": "weekly",
  "stats": {
    "total_completions": 18,
    "active_days": 6,
    "completion_rate": 0.86,
    "current_streak": 5,
    "best_dow": "수",
    "weak_dow": "일",
    "best_hour_bucket": "아침",
    "top_habits": {"운동": 6, "독서": 4, "명상": 3}
  },
  "insight": "🔥 정말 잘하고 계세요! 7일 중 6일이나 활동하셨네요 (86%).\n현재 5일 연속 달성 중! ...",
  "recommendations": [
    "이번 일요일에 작은 일정 1개 완료하기",
    "6일째 연속 달성 도전",
    "새 캐릭터 모으기 — 상점 둘러보기"
  ]
}
```

### 메모리 자동 카테고리화
```
POST /api/memory/auto-add        — 텍스트만 보내면 카테고리 + 중요도 자동
POST /api/memory/recategorize    — 기존 모든 메모리 재분류
```

자동 분류 카테고리 6종:
- `habit`, `preference`, `schedule`, `game_event`, `emotion`, `personal`
- 매치 안 되면 `conversation`

중요도 자동 산정:
- 카테고리 기본값 (personal=0.7, schedule=0.4 ...)
- + 길이 보정 (50자↑ +0.1)
- + 강조 단어 ("중요","꼭","절대"...) +0.15

### WebSocket 실시간 알림
```
WS   /ws/notifications           — 클라이언트 연결, 백그라운드 push 시작
POST /api/notifications/test     — 디버그용 즉시 push
```

푸시 메시지 타입:
- `connected` : 연결 확인
- `suggestion`: 능동 추천 변화 시 (기존 `/api/proactive/suggestions` 의 push 버전)
- `alarm`     : 일정 알람 시간 도달 (HH:MM 매치)
- `pong`      : ping 응답
- `test`      : 디버그

폴링(매번 GET 요청) → 푸시(서버가 변화 감지해서 보냄) 으로 효율 + UX 향상.

---

## 🧠 인사이트 리포트 작동 방식

```
사용자 데이터 (HabitCompletion)
        ↓
_gather_stats(7 또는 30 days)
  - 요일별/시간대별 집계
  - streak, top_habits, completion_rate
        ↓
        ├─ LLM 가능 (Ollama) ─→ _llm_insight()
        │   "친근한 코치 톤으로 한국어 4-6문장"
        │
        └─ LLM 미설치/실패 ─→ _template_insight()
            규칙 기반 자연어 (격려 + 패턴 + 제안)
        ↓
+ _action_recommendations() 3가지 행동
        ↓
JSON 응답
```

LLM 없어도 **항상 동작** (graceful degradation). 사용자가 ollama 안 켰을 때도 통계 + 템플릿 분석은 보임.

---

## 📡 WebSocket 흐름

```
[클라]                       [서버]
  │                            │
  │── connect ws ──────────────→│
  │← {type:"connected"}         │
  │                            │── 백그라운드 폴러 시작 (30초 주기)
  │                            │
  │  ... 시간 흐름 ...           │
  │                            │── 능동 추천 변화 감지
  │←{type:"suggestion",data:[]}─│
  │                            │
  │  ... HH:MM 도달 ...          │
  │                            │── habit.times 매치 + repeat_days 매치
  │←{type:"alarm",data:{...}}──│   (오늘 같은 알람 중복 방지)
  │                            │
  │── ping ───────────────────→│
  │← pong                      │
```

날짜 바뀌면 알람 중복 추적 자동 리셋.

---

## ✅ 통합 검증 (`test_d_features.py`)

기존 7개 + W5 3개 = **총 10개 카테고리** 자동 점검:
1. DB 모델 / 마이그레이션
2. AI 에이전트 도구 18개
3. 게임 상태 도구 5개
4. 능동 추천 + 패턴 분석
5. RAG 메모리
6. 외부 연동 (Google Calendar/Email)
7. 캘린더 API
8. **W5: 인사이트 리포트** ← NEW
9. **W5: 메모리 자동 카테고리화** ← NEW
10. **W5: WebSocket 모듈** ← NEW

---

## 🚀 사용자 실행

```powershell
cd C:\Users\guswl\OneDrive\Desktop\Plan-quest\backend

# 새 의존성 X (FastAPI 의 WebSocket 은 기본 포함, langchain 도 있음)

# 통합 검증
python test_d_features.py

# 백엔드 실행
python main.py
```

### 빠른 API 테스트
```powershell
# 즉시 동작 (LLM 불필요)
curl http://localhost:8000/api/insights/quick

# 자연어 리포트 (Ollama 켜져 있으면 LLM 사용)
curl http://localhost:8000/api/insights/weekly

# 메모리 자동 추가
curl -X POST http://localhost:8000/api/memory/auto-add `
  -H "Content-Type: application/json" `
  -d '{"text":"운동 매일 아침 6시에 꼭 하기"}'
# → {"chroma_id":"...", "auto_category":"habit", "auto_importance":0.75}
```

### WebSocket 테스트 (브라우저 콘솔)
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/notifications');
ws.onmessage = (e) => console.log(JSON.parse(e.data));
ws.onopen = () => console.log('연결됨');
// 30초마다 또는 알람 시간/추천 변화 시 자동 메시지 도착
```

---

## 📊 D 역할 누적 (W3 → W5)

| 주차 | 핵심 기능 |
|------|----------|
| W3 D1-3 | LangChain ReAct 에이전트 + 9개 기본 도구 |
| W3 D4-6 | RAG 메모리 (ChromaDB + 임계값) |
| W3 D7-10 | Google Calendar/Gmail 스캐폴드 |
| W4 D1-3 | 게임 상태 인식 도구 6개 추가 (총 15개) |
| W4 D4-6 | 능동 추천 + 패턴 분석 + 개인화 컨텍스트 |
| W4 D7-10 | 캘린더 히트맵 API + 완료 기록 도구 (총 18개) |
| **W5 D1-2** | **AI 인사이트 리포트 (LLM)** |
| **W5 D3** | **메모리 자동 카테고리화** |
| **W5 D4** | **WebSocket 실시간 알림** |
| **W5 D5** | **통합 검증 + 문서** |

---

## 🤝 협업 인터페이스 (다른 팀원이 활용)

W5 새 추가 부분:

| 팀 | API | 용도 |
|----|-----|------|
| 프론트 (대시보드) | `GET /api/insights/weekly` | 주간 리포트 화면 |
| 프론트 (위젯) | `GET /api/insights/quick` | 메인 화면 한 줄 요약 |
| 프론트 (실시간) | `WS /ws/notifications` | 토스트/배지 자동 갱신 |
| 알림 시스템 | `WS /ws/notifications` | 일정 알람 푸시 |

폴링 코드 → WebSocket 으로 교체하면 즉시 적용 가능.

---

## 🎯 다음 단계 후보 (W6+)

W5 까지 끝난 시점에서 D 가 갈 수 있는 방향:
1. **Voice I/O** — TTS/STT (음성 비서)
2. **OAuth 실제 연동** — Google Calendar/Gmail credentials.json 적용
3. **모델 파인튜닝** — 사용자 대화로 LoRA (W4 에서 제외했지만 추가 가능)
4. **다중 사용자** — 현재 single-user 구조 → multi-user
5. **모바일 PWA** — 백엔드 push notification (FCM/APNs)

---

이상 D 역할 W5 완료. W3-W5 통틀어 14일치 작업 + 통합 검증 + 문서 마무리.
