# 🎉 Week 3-4 완료 — Team Member D

**완료일:** 2026-05-02
**범위:** Week 3 Day 4-10 + Week 4 (D 역할만)
**제외:** LoRA 파인튜닝 (D 역할 아님), 도감 UI / 퀘스트 UI (협업)

---

## 📂 새로 추가된 파일

```
backend/
├── memory_engine.py              ★ ChromaDB RAG 메모리 엔진
├── proactive_ai.py               ★ 능동 추천 + 패턴 분석
├── add_flame_dino.py             (이전 작업) 캐릭터 등록
├── migrate_db.py                 (UserMemory 컬럼 추가)
├── routers/
│   ├── memory.py                 ★ /api/memory/*
│   └── proactive.py              ★ /api/proactive/*
├── tools/
│   └── game_state_tools.py       ★ 6개 게임 상태 도구
├── integrations/
│   ├── __init__.py
│   ├── google_calendar.py        ★ Google Calendar 스캐폴드
│   ├── email_client.py           ★ Gmail / IMAP 스캐폴드
│   └── README_연동가이드.md       ★ OAuth 설정 단계별 안내

backend/ (수정)
├── models.py                     UserMemory 테이블 추가
├── main.py                       memory + proactive 라우터 등록
├── agent_core.py                 게임 상태 도구 6개 등록 + 개인화 컨텍스트 주입
└── tools/
    ├── calendar_tools.py         실 연동 시도 → 실패 시 mock fallback
    └── email_tools.py            동일

frontend/ — 변경 없음 (D 역할 아님)
```

---

## 🧠 W3 Day 4-6: RAG 메모리

ChromaDB 영속 저장소에 사용자 대화/맥락 벡터 저장.
새 질문이 들어오면 의미 유사한 과거 메모리를 검색해 AI 응답에 주입.

**저장 위치:** `~/chroma_db/` (자동 생성)
**임베딩 모델:** Ollama `nomic-embed-text` (없으면 `qwen2.5:latest` 폴백)

### 임계값 엔진
오래되고 덜 중요한 메모리 자동 정리:
```
importance < 0.3
AND created_at < (오늘 - 30일)
AND (last_accessed is None OR last_accessed < 오늘 - 7일)
```
자주 검색되는 메모리는 `access_count` 증가로 보호됨.

### 사용
```bash
# 메모리 추가
curl -X POST http://localhost:8000/api/memory/add \
  -H "Content-Type: application/json" \
  -d '{"text": "운동 좋아함", "memory_type": "preference", "importance": 0.7}'

# 검색
curl -X POST http://localhost:8000/api/memory/search \
  -H "Content-Type: application/json" \
  -d '{"query": "내가 뭘 좋아해?", "top_k": 3}'

# 통계
curl http://localhost:8000/api/memory/stats

# 정리 실행 (dry_run 으로 미리 확인)
curl -X POST http://localhost:8000/api/memory/cleanup \
  -H "Content-Type: application/json" -d '{"dry_run": true}'
```

AI 채팅 시 자동으로 작동 — 별도 호출 불필요.

---

## 🔌 W3 Day 7-10: 외부 연동 스캐폴드

**현재 상태:** credentials.json 없으면 mock 데이터 반환 (Week 1-2 동작 그대로 유지).
**연동 시:** 자격증명 받아서 끼우면 즉시 실 데이터 반환.

```python
# 도구가 자동으로 판단:
def search_calendar(query):
    real = _try_real_calendar(query)   # 연동되면 실 데이터
    if real is not None:
        return real
    # 안 되면 mock                       <- 현재 상태
```

### 연동 절차
[backend/integrations/README_연동가이드.md](backend/integrations/README_연동가이드.md) 참조.

요약:
1. Google Cloud Console → OAuth client ID 생성 → JSON 다운로드
2. `~/.plan-quest/credentials.json` 위치에 저장
3. 첫 실행 시 브라우저 동의 → 토큰 자동 저장
4. 끝. 도구가 자동으로 실 데이터 사용

---

## 🎮 W4 D 역할: 게임 상태 인식 AI

게임 흐름이 "하트 → 나무 → 캐릭터" 로 변경되어, AI 가 이 데이터를 이해해야 함.

### 6개 새 도구
| 도구 | AI 가 답할 수 있는 질문 |
|------|----------------------|
| `get_user_stats` | "내 하트 몇 개야?", "레벨 뭐야?" |
| `get_placed_characters` | "정원에 누가 있어?", "배치한 거 보여줘" |
| `get_owned_characters` | "보유한 거 뭐 있어?", "안 놓은 애들?" |
| `get_growing_trees` | "나무들 어떻게 자라?", "수확할 거 있어?" |
| `get_shop_recommendations` | "뭐 사면 좋을까?" |
| `get_garden_summary` | "내 진행 상황 어때?" |

### 능동 추천 (사용자가 묻기 전에 먼저)
```
GET /api/proactive/suggestions
→ [
    {"type": "harvest", "priority": 5, "title": "💗 하트 7개 수확 가능!", ...},
    {"type": "place_character", "priority": 3, "title": "배치 안 한 캐릭터 2마리", ...},
    {"type": "habit_streak", "priority": 4, "title": "🔥 5일 연속!", ...}
  ]
```

프론트는 이 결과를 토스트/배지/알림으로 표시 (협업 영역).

### 패턴 분석
```
GET /api/proactive/insights
→ {
    "total_habits": 5,
    "avg_streak": 3.2,
    "best_habit": "아침 운동",
    "best_streak": 7,
    "weakest_time": "밤",  ← 이 시간대 일정이 적음
    "completion_rate_today": 0.6
  }
```

### 개인화 컨텍스트 (AI 자동 주입)
모든 AI 채팅에 자동으로 다음 컨텍스트 주입:
```
[사용자 현재 상태]
- Lv.2, 하트 7
- 보유 캐릭터 3, 배치 1
- 일정 5개, 오늘 달성률 60%, 최고 연속 5일

[과거 관련 맥락]
- (preference) 운동 좋아함
- (habit) 아침 운동 7일 연속

사용자: 오늘 뭐 하면 좋을까?
```

---

## 🚀 실행 가이드

### 처음 한 번만

```powershell
cd C:\Users\guswl\OneDrive\Desktop\Plan-quest\backend

# 1) 새 의존성 설치
pip install -r requirements.txt

# 2) DB 마이그레이션 (UserMemory 컬럼 추가)
python migrate_db.py

# 3) 임베딩 모델 받기 (선택 - 없어도 동작)
ollama pull nomic-embed-text
```

### 매번

```powershell
# 백엔드
python main.py

# 프론트 (이미 켜져 있으면 hot-reload)
cd ..\frontend
npm start
```

---

## ✅ 완료 체크리스트

- [x] **W3 D4-6** RAG 메모리 (ChromaDB + 임계값 엔진)
- [x] **W3 D7-10** Google Calendar/Gmail 스캐폴드 + 연동 가이드
- [x] **W4 D1-3** 게임 상태 인식 AI 도구 (6개)
- [x] **W4 D4-6** 능동 추천 + 패턴 분석 + 개인화
- [x] **W4 D7-10** 통합 — agent_core 가 메모리 + 게임 상태 + 외부 연동(준비됨) 모두 사용
- [x] DB 마이그레이션 스크립트 갱신
- [x] 모든 파일 syntax 통과
- [x] 문서화

---

## 🤝 협업 인터페이스 (다른 팀원이 갖다 쓸 수 있게)

**도감 UI 담당이 쓸 API:**
- `GET /api/shop?category=character` — 모든 캐릭터 목록 (소유 여부 포함)
- 도감 자체 테이블이 필요하면 협의 후 D 가 추가

**퀘스트 UI 담당이 쓸 API:**
- `GET /api/proactive/suggestions` — 능동 추천 (퀘스트 UI 의 데이터 소스로 활용 가능)
- 퀘스트 모델은 게임 디자인 정해지면 협의 후 D 가 백엔드 추가

**프론트 알림/토스트:**
- `GET /api/proactive/suggestions` 를 1분마다 폴링하거나
- 액션 후 (수확, 구매 등) 호출

---

## 🎯 D 의 다음 단계 후보

1. **WebSocket 푸시** — 능동 추천을 폴링 대신 푸시로 전송
2. **AI 음성 응답** — TTS 통합 (Coqui/MeloTTS)
3. **메모리 시각화** — 어떤 맥락이 있는지 사용자에게 보여주기
4. **외부 연동 실제 OAuth** — 사용자가 credentials 받으면 D 가 마무리

---

이상 Week 3-4 D 역할 완료.
