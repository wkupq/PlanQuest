# Plan-Quest — Week 3-4 로드맵 (Team Member D 전용)

**최종 업데이트:** 2026-05-02
**담당:** Team Member D (AI 백엔드)
**범위 변경 사유:**
1. 게임 진행 방식 변경 (하트 → 나무 → 캐릭터 배치)
2. 협업 영역 (도감 UI, 퀘스트 UI) 제외
3. LoRA 파인튜닝은 D 담당 아님 → 제외

---

## 🎮 변경된 게임 흐름

```
일정 추가 → 나무 심기 (씨앗)
        ↓
일정 완료 → 나무 성장 (씨앗 → 새싹 → 작은나무 → 큰나무)
        ↓
나무에서 하트 수확 → UserProfile.hearts 증가
        ↓
상점에서 하트로 캐릭터 구매 → OwnedItem
        ↓
캐릭터를 배치도 위에 배치 → PlacedItem (grid_x, grid_y)
        ↓
배치된 캐릭터들이 정원을 꾸밈
```

**D가 만들 AI 에이전트는 이 흐름 전체를 이해하고 사용자와 대화해야 함.**

---

## 📋 D 담당 범위 (이번 작업)

### Week 3 — 진행 중

#### Day 1-3: AI 에이전트 코어 ✅ **완료**
- `agent_core.py`, `tools/habit_tools.py`, `tools/calendar_tools.py`, `tools/email_tools.py`
- LangChain ReAct + Qwen2.5

#### Day 4-6: RAG 메모리 (ChromaDB) — **이번에 진행**
사용자 대화/맥락을 벡터 DB에 저장 → 유사 검색으로 개인화 응답

**파일:**
- `backend/memory_engine.py` — ChromaDB 래퍼 클래스
- `backend/routers/memory.py` — REST API
- `backend/models.py` — `UserMemory` 테이블 추가
- `backend/agent_core.py` — 메모리 통합 (대화 시작 시 컨텍스트 주입)

**임계값 엔진:**
오래된/덜 중요한 메모리 자동 정리 (DB 비대화 방지)

#### Day 7-10: Google Calendar / Gmail 연동 — **이번에 진행 (스캐폴드만)**
**상태:** 코드 자리만 만들고, OAuth credentials 받아서 끼워 넣을 수 있도록.
실제 OAuth 흐름은 **연동 시점에 사용자가 추가**.

**파일:**
- `backend/integrations/__init__.py`
- `backend/integrations/google_calendar.py` — 클래스 골격 + TODO 주석
- `backend/integrations/email_client.py` — 동일
- `backend/integrations/README_연동가이드.md` — Google Cloud Console 설정 + credentials.json 위치

**현재 동작:**
연동 전엔 `tools/calendar_tools.py`, `tools/email_tools.py` 가 mock 데이터 반환 (Day 1-3 그대로).
연동 시점에 integrations 의 실제 클라이언트로 교체.

---

### Week 4 — D 역할 재정의

원래 Week 4 계획 (도감/퀘스트/LoRA) 는 **D 담당 아님**:
- 도감 UI: 프론트 담당 (협업)
- 퀘스트 UI: 프론트 + 게임 디자인 담당 (협업)
- LoRA 파인튜닝: AI 연구 담당 (D 아님)

**대신 D 가 게임 흐름 변경에 맞춰 추가 작업:**

#### Day 1-3: 게임 상태 인식 AI 도구
사용자가 "내 정원에 캐릭터 몇 마리 있어?" "하트 얼마나 모았어?" "다음에 뭐 사면 좋을까?" 같은 질문 가능하게.

**파일:**
- `backend/tools/game_state_tools.py` — 6개 새 도구
  - `get_user_stats()` — 하트/레벨 조회
  - `get_placed_characters()` — 배치된 캐릭터 목록
  - `get_owned_characters()` — 보유 (배치 안 된) 목록
  - `get_growing_trees()` — 자라는 나무 + 진행도
  - `get_shop_recommendations()` — 살 만한 캐릭터 추천
  - `get_garden_summary()` — 정원 한 줄 요약
- `agent_core.py` 업데이트 — 새 도구 등록

#### Day 4-6: 능동적 추천 + 개인화 응답
사용자가 묻기 전에 AI가 패턴 보고 먼저 제안.

**파일:**
- `backend/proactive_ai.py` — 패턴 분석 + 추천 엔진
  - 일정 달성 패턴 → 약한 시간대 발견 → 격려
  - 보유 캐릭터 분포 → 다음 추천
  - 메모리 + 게임 상태 결합한 컨텍스트 빌더

#### Day 7-10: 통합 + 테스트
- `agent_core.py` 최종 통합
- 게임 상태 + 메모리 + 외부 연동 (mock) 모두 함께 동작
- E2E 테스트 시나리오

---

## 🤝 협업 영역 (D 가 손대지 않음)

| 영역 | 담당 (예상) | D 가 할 일 |
|------|-------------|-----------|
| 도감 UI (`PokedexPanel.js`) | 프론트엔드 | API 만 노출 (`/api/pokedex` — 기존 placement 라우터로 충분할 수도) |
| 퀘스트 UI (`QuestPanel.js`) | 프론트 + 게임 디자인 | 데이터 모델만 합의 후 백엔드 라우터는 협업으로 |
| LoRA 파인튜닝 | AI 연구 담당 | 데이터 수집 도구만 노출 (UserMemory 테이블) |
| 캐릭터 그래픽 | 디자인 | `frontend/public/images/characters/` 에 PNG 두면 D 의 AI 가 인지 |

---

## 📦 추가 의존성

```bash
pip install chromadb==0.4.24
pip install google-auth-oauthlib==1.2.0      # Google API 스캐폴드용
pip install google-auth-httplib2==0.2.0
pip install google-api-python-client==2.105.0
```

---

## ✅ 완료 기준

D 작업 완료 시점에서:
1. **AI 가 게임 상태를 인지함** — "캐릭터 몇 마리야?" 답변 가능
2. **AI 가 과거 대화를 기억** — RAG 메모리로 컨텍스트 검색
3. **Google API 연동 자리 준비됨** — credentials.json 만 넣으면 동작
4. **메모리 임계값 엔진 동작** — 오래된 메모리 자동 정리
5. **능동적 추천** — 사용자에게 먼저 제안

도감/퀘스트/LoRA 는 다른 담당이 맡으면 D 의 backend 와 자연스럽게 연결되도록 데이터 모델/엔드포인트만 깔끔히 노출.
