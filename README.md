# 🌳 Plan-Quest (습관의 숲)

> **AI 비서와 함께 자라는 정원** — 습관 관리를 게임으로 만든 캡스톤 프로젝트

일정을 등록하면 씨앗이 심어지고, 완료할 때마다 나무가 자라며, 하트를 모아 귀여운 캐릭터를 정원에 배치하는 게임형 습관 관리 앱. 백엔드는 LangChain + Ollama 기반 로컬 AI 에이전트로 작동.

**GitHub**: https://github.com/wkupq/Plan-quest-UI

---

## 🎮 게임 흐름

```
일정 추가 → 🌰 씨앗 심어짐 (배치도)
   ↓
일정 완료 → 🌱→🌿→🌳 나무 성장 (4단계)
   ↓
나무 클릭 → ❤️ 하트 수확
   ↓
🛍️ 상점에서 캐릭터 구매 (하트 사용)
   ↓
🎒 인벤토리 → 배치도에 캐릭터 배치
   ↓
배치된 캐릭터가 시간이 지나면 자동으로 하트 생성 (등급별 차등)
   ↓
모은 하트로 더 비싼 캐릭터 구매 → 정원 꾸미기
```

---

## ⚡ 빠른 시작

### 1. 백엔드
```powershell
cd backend
pip install -r requirements.txt
python migrate_db.py        # DB 스키마 마이그레이션
python main.py              # http://127.0.0.1:8000
```

### 2. 프론트엔드 (다른 터미널)
```powershell
cd frontend
npm install
npm start                   # http://localhost:3000
```

### 3. (선택) Ollama AI
```powershell
ollama pull qwen2.5:latest
ollama pull nomic-embed-text    # RAG 메모리 임베딩
ollama serve
```

---

## 🎯 주요 기능

### 🌱 핵심 게임 시스템
- **아이소메트릭 배치도** (7x5 = 35 타일)
- **씨앗/나무 4단계 성장** (씨앗 → 새싹 → 어린나무 → 큰나무, 사용자 일러스트 PNG 지원)
- **씨앗 클릭** → 일정 정보 모달 (반복 요일, 시간, streak, 다음 알람 카운트다운)
- **시간 카운트다운 배지** 각 나무 위에 1분마다 갱신
- **빌보드 렌더링** — 캐릭터가 항상 화면에 똑바로 (진짜 2.5D)

### 🐾 캐릭터 시스템 (14마리)
| 등급 | 수 | 시간당 하트 | 배지 색 |
|------|---:|-----------:|---------|
| Common | 8 | 6h / 1하트 | — |
| Rare | 3 | 4h / 2하트 | 🔵 파랑 |
| **Unique** | 3 | 3h / 3하트 | 🟣 보라 |

- **시간당 하트 자동 생성** — 배치된 캐릭터마다 등급별 주기로 ❤️ 누적
- **수확** — 캐릭터 클릭 → 모달에서 하트 받기
- **이동/회수** — 다른 칸으로 옮기거나 인벤토리로 회수 (보유 유지)
- **이름 자동 매칭 + 자동 폴백** — PNG 없으면 emoji 사용

### 🤖 AI 에이전트 (LangChain ReAct + Qwen2.5)
사용자의 자연어 질문에 18개 도구 자동 선택 → 답변.

| 카테고리 | 도구 수 | 예시 |
|---------|--------:|------|
| 습관 | 3 | "내 일정 뭐야?", "운동 완료했어" |
| 캘린더 | 3 | "내일 회의 있어?", "주간 일정" |
| 이메일 | 3 | "중요한 메일", "이메일 분류" |
| 게임 상태 | 6 | "정원 누가 있어?", "뭐 사면 좋을까?" |
| 완료 기록 분석 | 3 | "이번 주 몇 번 했어?", "내가 언제 잘해?" |

### 💬 슬래시 커맨드 (LLM 우회 — 즉시 실행)
```
/help, /hearts, /summary, /today, /list, /history,
/pattern, /stats, /suggest, /add <제목>, /complete <키워드>
```

### 🧠 RAG 메모리 (ChromaDB)
- 모든 대화 자동 저장 → 벡터 검색으로 과거 맥락 자동 주입
- **자동 카테고리화** (habit/preference/schedule/game_event/emotion/personal)
- **임계값 엔진** — 중요도 낮고 오래된 메모리 자동 정리

### 📅 캘린더 (히트맵 + 디테일)
- 월별 5단계 히트맵 (완료 수에 따라 색 진해짐)
- 날짜 클릭 → 예정/완료 일정 + 받은 하트 표시
- 통계: 달성일, 총 완료, 🔥 연속, 받은 하트

### 📈 AI 인사이트 리포트 (LLM)
- 주간/월간 자연어 분석 ("강한 요일은 수요일이에요...")
- 통계 + 격려 + 다음 주 제안
- LLM 없을 때 템플릿 폴백

### 🔔 WebSocket 실시간 알림
- 일정 알람 시간 도달 시 자동 푸시
- 능동 추천 변화 시 푸시 (폴링 X)
- `ws://localhost:8000/ws/notifications`

### 💡 자동 일정 추천 + 빈 시간대
- 사용자 패턴 + 라이브러리 기반 추천 (Top N)
- 빈 시간대 분석 (아침/낮/저녁/밤)

### 👍 응답 피드백 학습
- 사용자가 AI 응답에 좋다/나쁘다 평가
- 메모리에 importance 다르게 저장 → 다음 응답에 반영

---

## 🛠️ 기술 스택

### 백엔드
- **FastAPI 0.104** + Uvicorn + Pydantic
- **SQLAlchemy 2.0** + SQLite
- **LangChain 0.1.13** + Qwen2.5 (Ollama 로컬)
- **ChromaDB 0.4.24** + nomic-embed-text (벡터 메모리)
- **WebSocket** (실시간 푸시)
- Google API 스캐폴드 (Calendar/Gmail OAuth)

### 프론트엔드
- **React 18** + Hooks
- Axios (HTTP) + WebSocket
- CSS 변환 기반 아이소메트릭 + 빌보드 합성

---

## 📁 프로젝트 구조

```
Plan-quest/
├── backend/
│   ├── main.py                    # FastAPI 앱 + lifespan
│   ├── agent_core.py              # LangChain ReAct 에이전트 (18 도구)
│   ├── memory_engine.py           # ChromaDB RAG 메모리
│   ├── proactive_ai.py            # 능동 추천 + 패턴 분석
│   ├── slash_commands.py          # 챗봇 슬래시 커맨드 12개
│   ├── ollama_manager.py          # Ollama 자동 시작/종료
│   ├── models.py                  # DB 모델 (UserProfile, Habit, HabitCompletion,
│   │                              #  ShopItem, OwnedItem, PlacedItem, TreeOnMap, UserMemory)
│   ├── schemas.py                 # Pydantic 스키마
│   ├── database.py                # SQLite 연결
│   ├── seed_data.py               # 상점 초기 데이터 (14 캐릭터)
│   ├── migrate_db.py              # DB 스키마 마이그레이션
│   │
│   ├── routers/
│   │   ├── user.py                # /api/user (+ 디버그용 dev/add-hearts)
│   │   ├── habits.py              # /api/habits CRUD + complete
│   │   ├── trees.py               # /api/trees + harvest + move
│   │   ├── shop.py                # /api/shop + buy
│   │   ├── placement.py           # /api/placed-items + move + harvest
│   │   ├── chat.py                # /api/chat/stream (SSE) + 슬래시 dispatch
│   │   ├── memory.py              # /api/memory/* (RAG)
│   │   ├── proactive.py           # /api/proactive/{suggestions,insights,context}
│   │   ├── calendar.py            # /api/calendar/{month,day} (히트맵)
│   │   ├── insights.py            # /api/insights/{weekly,monthly,quick}
│   │   ├── notifications.py       # WS /ws/notifications
│   │   ├── suggestions.py         # /api/suggestions/{habits,empty-slots,best-time}
│   │   └── feedback.py            # /api/feedback/{rate,recent,stats}
│   │
│   ├── tools/                     # AI 에이전트 도구
│   │   ├── habit_tools.py         # 3개
│   │   ├── calendar_tools.py      # 3개 (Google Calendar fallback → mock)
│   │   ├── email_tools.py         # 3개 (Gmail API fallback → mock)
│   │   └── game_state_tools.py    # 9개 (게임 상태 + 완료 기록 분석)
│   │
│   ├── integrations/              # 외부 연동 스캐폴드
│   │   ├── google_calendar.py     # OAuth 흐름
│   │   ├── email_client.py        # Gmail API + IMAP fallback
│   │   └── README_연동가이드.md
│   │
│   ├── test_d_features.py         # 13개 통합 검증
│   │
│   └── (테스트/관리 스크립트)
│       ├── reset_shop.py          # 상점 wipe + 재등록
│       ├── add_new_chars.py       # 캐릭터 증분 추가
│       ├── rename_chars.py        # 캐릭터 이름 갱신
│       ├── update_rarities.py     # 등급 갱신
│       ├── reset_owned_double_price.py  # 보유 초기화 + 가격 ×2
│       └── add_hearts.py          # 테스트용 하트 직접 추가
│
└── frontend/
    ├── public/
    │   └── images/
    │       ├── characters/        # 14 캐릭터 PNG
    │       └── seeds/             # 새싹 PNG (사용자 일러스트)
    │
    └── src/
        ├── App.js                 # 메인 + 모달 라우팅
        ├── api.js                 # Axios 함수들
        │
        ├── components/
        │   ├── IsometricMap.js    # 배치도 + 빌보드 레이어
        │   ├── TreeIcon.js        # 4단계 나무 SVG/PNG
        │   ├── CharacterInfoModal.js  # 캐릭터 액션 (이동/회수/수확)
        │   ├── TreeInfoModal.js   # 나무 정보 + 카운트다운 + 수확/이동/삭제
        │   ├── CalendarPanel.js   # 히트맵 + 날짜 디테일
        │   ├── ChatDashboard.js   # SSE 스트리밍 채팅
        │   ├── HabitPanel.js      # 일정 목록
        │   ├── HabitForm.js       # 일정 추가
        │   ├── ShopPanel.js       # 상점 (등급 배지)
        │   ├── InventoryPanel.js  # 인벤토리
        │   ├── RoutinePanel.js    # 달성률 대시보드
        │   ├── OllamaPopup.js     # Ollama 자동 설치 안내
        │   └── Toast.js
        │
        ├── utils/timeUtils.js     # 다음 알람 카운트다운
        └── styles/global.css      # 아이소메트릭 + 빌보드 CSS
```

---

## 🔌 API 요약

### 게임
```
GET  /api/user
POST /api/habits                          GET /api/habits
POST /api/habits/{id}/complete            DELETE /api/habits/{id}
GET  /api/trees
POST /api/trees/{id}/harvest              PATCH /api/trees/{id}/position
GET  /api/shop                            POST /api/shop/{id}/buy
GET  /api/placed-items                    POST /api/placed-items
PATCH /api/placed-items/{id}/position     POST /api/placed-items/{id}/harvest
DELETE /api/placed-items/{id}
```

### AI / 분석
```
POST /api/chat/stream                     # SSE 채팅 + 슬래시 커맨드
GET  /api/chat/tools                      # 등록된 도구 목록

POST /api/memory/{add,search,auto-add,recategorize}
GET  /api/memory/stats                    POST /api/memory/cleanup
DELETE /api/memory/{chroma_id}

GET  /api/proactive/{suggestions,insights,context}
GET  /api/calendar/{month,day}
GET  /api/insights/{weekly,monthly,quick}
GET  /api/suggestions/{habits,empty-slots,best-time}
POST /api/feedback/rate                   GET /api/feedback/{recent,stats}
WS   /ws/notifications                    # 실시간 푸시
```

---

## 👥 팀 구성 (캡스톤)

| 팀원 | 모듈 | 핵심 과제 | 주차 |
|------|------|-----------|------|
| **A** | `ollama_runner` · `agent` · `rag/` · `LoRA(train/merge/GGUF)` | context RAG 3단계 연결 + GIL 우회 + GGUF 변환 | W1(RAG) · W4(데이터) · W5(LoRA) |
| **B** | `calendar` · `email` · `OAuth` · `masking` · `tenacity` · 설치가이드 | OAuth 토큰 갱신 + 증분 동기화 + Rate Limit | W1(API) · W2(연동) · W3(보안) |
| **C** | `memory` · `scheduler` · `ChromaDB` · `BM25` · `SQLCipher` · `Alembic` · `backup` | 임계값 로직 + 정합성 검사 + SQLCipher+Alembic 연동 | W1(DB) · W2(메모리) · W3(보안) · W5(백업) |
| **D** (본 저장소 담당) | `dashboard` · `chatbot` · `game_screen` · `game/` · `PyInstaller` · `ollama_manager` | 패키징 의존성 충돌 + 게임 UI 성능 | W1(UI) · W3~4(게임) · W5(패키징) |

### D 역할 진척도 (W1 → W6)
- ✅ W1: 게임 화면 / 대시보드 / 챗봇 UI 기본 구조
- ✅ W2: 일정 관리 + 나무 성장 시스템 + SSE 스트리밍 채팅
- ✅ W3~4: 게임 화면 (아이소메트릭 배치도 7×5, 빌보드 렌더링, 캐릭터/나무 모달)
- ✅ W3~4: 챗봇 (Ollama 자동 관리, agent 통합, 슬래시 커맨드 12개)
- ✅ W5: 캘린더 히트맵 + 인사이트 대시보드 + WebSocket 알림
- ✅ W5~: `ollama_manager` 자동 시작/종료, graceful shutdown
- ✅ W6: 자동 일정 추천 + 응답 피드백 시스템 + 14 캐릭터 등급 시스템
- ⏳ W5~ 진행 중: PyInstaller 패키징 + 의존성 충돌 해결

상세 문서:
- [`WEEK3_ROADMAP.md`](WEEK3_ROADMAP.md), [`WEEK3-4_ROADMAP_D.md`](WEEK3-4_ROADMAP_D.md)
- [`WEEK4_COMPLETE_D.md`](WEEK4_COMPLETE_D.md)
- [`WEEK5_COMPLETE_D.md`](WEEK5_COMPLETE_D.md)
- [`WEEK6_COMPLETE_D.md`](WEEK6_COMPLETE_D.md)
- [`AGENT_ARCHITECTURE.md`](AGENT_ARCHITECTURE.md)

---

## 🧪 통합 검증

```powershell
cd backend
python test_d_features.py
```

13개 카테고리 자동 점검:
1. DB 모델 / 마이그레이션
2. AI 에이전트 도구 18개
3. 게임 상태 도구
4. 능동 추천 + 패턴 분석
5. RAG 메모리
6. Google Calendar/Email (미연동 시 ⚠️)
7. 캘린더 API
8. 인사이트 리포트 (W5)
9. 메모리 자동 카테고리화 (W5)
10. WebSocket 모듈 (W5)
11. 자동 일정 추천 (W6)
12. 슬래시 커맨드 (W6)
13. 피드백 시스템 (W6)

---

## 🎯 게임 플레이 팁

1. **첫 일정** 등록 → 씨앗 심김 → 매일 완료 → 나무 자람
2. **연속 7일** 달성하면 보너스 하트 +1
3. 첫 캐릭터로 **불꽃포메 (6H)** 또는 **카피바라 (8H)** 추천
4. 캐릭터 배치 후 **시간 지나면 ❤️ 자동 누적** — 자주 들어와서 수확
5. **유니크 등급** (별자리양 24H, 우주거북 24H, 무지개여우 20H) 은 시간당 3하트로 최고 가성비
6. **챗봇에 `/suggest`** 입력하면 AI 가 다음 일정 추천

테스트용 명령:
```powershell
python backend/add_hearts.py 100         # 100 하트 즉시 추가
python backend/add_hearts.py --level 5    # 레벨 5로
python backend/add_hearts.py --reset      # 0 으로 리셋
```

---

## 📚 추가 문서

- `WEEK6_COMPLETE_D.md` — Week 6 D 역할 상세
- `AGENT_ARCHITECTURE.md` — AI 에이전트 아키텍처
- `IMPLEMENTATION_COMPLETE.md` — 초기 구현 보고서
- `backend/integrations/README_연동가이드.md` — Google API OAuth 설정

---

## 📝 라이선스

캡스톤 프로젝트 — 학술 / 비상업 용도.

---

**제작**: Plan-Quest 팀 (D 역할: AI 백엔드)
**최종 업데이트**: 2026-05-13 (Week 6 완료)
