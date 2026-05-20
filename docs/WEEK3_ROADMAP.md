# Plan-Quest Project - Week 3-4 개발 로드맵

**최종 업데이트:** 2026-05-01  
**Team Member:** D  
**GitHub:** https://github.com/wkupq/Plan-quest-UI.git

---

## 📊 현재까지의 진행상황

### Week 1-2 완료 ✅

#### 구현된 기능:
- ✅ FastAPI 백엔드 기본 구조 (models, routers, database)
- ✅ React 18 아이소메트릭 맵 UI (8x8 그리드, 3D 타일)
- ✅ 일정/습관 관리 시스템 (CRUD)
- ✅ 펫/캐릭터 수집 시스템 (11개 이미지 기반 캐릭터)
- ✅ 일정 달성률 UI (SVG 원형 프로그레스 바)
- ✅ SSE 실시간 스트리밍 채팅
- ✅ Ollama 자동 관리 (설치 확인, 자동 시작/종료)
- ✅ Graceful Shutdown (SIGTERM/SIGINT 핸들러)
- ✅ GitHub 푸시 완료

#### 주요 파일:
```
backend/
├── main.py (FastAPI lifespan, Ollama 자동 관리)
├── models.py (UserProfile, Habit, ShopItem, OwnedItem, PlacedItem, TreeOnMap)
├── routers/
│   ├── chat.py (SSE 스트리밍, /api/chat/stream)
│   ├── habits.py (일정 CRUD)
│   ├── shop.py (상점)
│   ├── placement.py (아이템 배치)
│   └── user.py (유저 정보)
├── ollama_manager.py (Ollama 자동 관리)
└── requirements.txt (추가: httpx)

frontend/
├── src/
│   ├── App.js (Ollama 팝업 통합)
│   ├── components/
│   │   ├── ChatDashboard.js (SSE 스트리밍, 토큰 단위 출력)
│   │   ├── OllamaPopup.js (미설치/미실행 팝업)
│   │   ├── RoutinePanel.js (달성률 UI)
│   │   ├── IsometricMap.js (3D 캐릭터 렌더링)
│   │   └── ... (기타 컴포넌트)
│   └── styles/global.css (스트리밍 커서 애니메이션, 팝업 스타일)
```

#### 현재 DB 스키마:
- UserProfile: 단일 사용자 (hearts, level, total_hearts_earned)
- Habit: 일정/습관 (title, repeat_days, times, streak, completed_today)
- ShopItem: 상점 아이템 (11개 이미지 기반 캐릭터)
- OwnedItem: 구매한 아이템
- PlacedItem: 맵에 배치된 아이템
- TreeOnMap: 습관별 성장 나무

---

## 🎯 Week 3: AI 에이전트 코어 + RAG 메모리

### 목표
**단순 스트리밍 채봇 → 지능형 멀티태스킹 에이전트 변환**

### 세부 일정

#### Day 1-3: AI 에이전트 코어 구축
**목표:** LangChain ReAct 패턴 기반 다단계 추론 에이전트

**생성할 파일:**
```
backend/
├── agent_core.py           # NEW: LangChain ReAct 에이전트
├── tools/
│   ├── __init__.py
│   ├── habit_tools.py      # NEW: 일정 조회/생성 도구
│   ├── calendar_tools.py   # NEW: 캘린더 도구
│   └── email_tools.py      # NEW: 이메일 도구
└── requirements.txt        # 추가: langchain, langchain-community
```

**구현 내용:**
```python
# agent_core.py
from langchain.agents import AgentType, initialize_agent
from langchain.llms import Ollama
from langchain.tools import Tool

# ReAct 패턴: Reasoning + Acting
agent = initialize_agent(
    tools=[get_habit_tool, search_calendar_tool, search_email_tool],
    llm=Ollama(model="qwen2.5"),  # llama3.2 대신 Qwen2.5
    agent=AgentType.REACT_DOCSTRING,
    verbose=True
)
```

**테스트:**
- 사용자: "내일 회의 있고, 중요한 메일 있으면 알려줘"
- AI: 자동으로 calendar_tools + email_tools 호출 → 결과 통합 응답

**체크리스트:**
- [ ] pip install langchain langchain-community
- [ ] agent_core.py 구현
- [ ] 3개 Tool 함수 정의
- [ ] ReAct 프롬프트 작성
- [ ] Ollama 모델 Qwen2.5로 변경 (향상된 추론)
- [ ] routers/chat.py에서 기존 로직 대신 agent 사용
- [ ] /api/chat/stream 스트리밍 테스트

---

#### Day 4-6: RAG 메모리 파이프라인
**목표:** 사용자 맥락 학습 및 개인화 응답 제공

**생성할 파일:**
```
backend/
├── memory_engine.py        # NEW: ChromaDB 통합
├── routers/memory.py       # NEW: 메모리 API 엔드포인트
└── models.py 수정          # NEW: UserMemory 테이블 추가
```

**구현 내용:**
```python
# memory_engine.py
from chromadb import Client
from langchain.embeddings import OllamaEmbeddings

class MemoryEngine:
    def add_memory(self, user_id, text, metadata):
        """사용자 맥락 저장 (대화, 일정, 선호도)"""
        # ChromaDB에 벡터로 저장
    
    def search_context(self, user_id, query, top_k=3):
        """유사한 과거 맥락 검색"""
        # 벡터 검색으로 관련 과거 정보 반환
    
    def cleanup_old_memory(self, user_id, threshold=0.3):
        """메모리 임계값 엔진: 오래되고 덜 중요한 기억 정리"""
        # 자동 정리로 메모리 효율성 증대
```

**DB 추가:**
```python
# models.py
class UserMemory(Base):
    __tablename__ = "user_memory"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user_profile.id"))
    memory_type = Column(String)  # "habit", "preference", "conversation"
    content = Column(String)
    embedding = Column(JSON)
    importance_score = Column(Float)  # 임계값 엔진용
    created_at = Column(DateTime, default=datetime.utcnow)
```

**API 엔드포인트:**
- POST /api/memory/add: 새 맥락 저장
- GET /api/memory/search: 유사 맥락 검색
- DELETE /api/memory/cleanup: 오래된 메모리 정리

**효과:**
```
사용자: "지난번에 한 그 프로젝트 어떻게 됐어?"
→ 과거 맥락 자동 검색
→ "아, 그 XXX 프로젝트요! 현재 상태는..."
```

**체크리스트:**
- [ ] pip install chromadb
- [ ] memory_engine.py 구현
- [ ] UserMemory 테이블 마이그레이션
- [ ] 메모리 임계값 엔진 구현
- [ ] /api/memory/* 엔드포인트 구현
- [ ] 대화 기록 자동 저장 로직
- [ ] 테스트: AI가 과거 맥락을 기억하는가?

---

#### Day 7-10: Google Calendar + 이메일 API 연동
**목표:** 실제 사용자 데이터와 AI 통합

**Day 7-8: Google Calendar**
```
backend/integrations/google_calendar.py
- GoogleCalendarClient 클래스
- get_events(): 캘린더 이벤트 조회
- sync_to_db(): 캘린더 → Plan-Quest DB 동기화
```

**Day 9-10: 이메일 + 통합**
```
backend/integrations/email_client.py
- EmailClient 클래스 (Gmail API 또는 IMAP)
- get_important_emails(): 중요 이메일 필터링
- classify_emails(): AI 기반 자동 분류
```

**체크리스트:**
- [ ] Google Calendar API 키 생성
- [ ] GoogleCalendarClient 구현
- [ ] sync_to_db() 함수
- [ ] Gmail API 또는 IMAP 설정
- [ ] EmailClient 구현
- [ ] 중요 이메일 자동 분류
- [ ] 전체 통합 테스트

---

## 🎮 Week 4: 게임 UI 완성 + LoRA 파인튜닝 준비

### 목표
**게임 요소 완성 + AI 학습 데이터 축적**

### 세부 일정

#### Day 1-3: 도감 시스템 (Pokedex)
**목표:** 펫 수집 현황 시각화

**DB 추가:**
```python
class Pokedex(Base):
    __tablename__ = "pokedex"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user_profile.id"))
    shop_item_id = Column(Integer, ForeignKey("shop_items.id"))
    caught_count = Column(Integer, default=0)
    favorite = Column(Boolean, default=False)
```

**API:**
- GET /api/pokedex: 도감 현황 (수집률, 펫 목록)
- POST /api/pokedex/favorite: 즐겨찾기

**UI:**
```
frontend/src/components/PokedexPanel.js
- 전체 수집률 (%)
- 펫 목록 (그리드)
- 펫별 수집 횟수
- 즐겨찾기 기능
```

---

#### Day 4-6: 퀘스트 시스템
**목표:** 일일 미션 및 보상 시스템

**DB 추가:**
```python
class Quest(Base):
    __tablename__ = "quests"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user_profile.id"))
    title = Column(String)
    description = Column(String)
    progress = Column(Integer, default=0)
    target = Column(Integer)  # 완료 목표
    reward_hearts = Column(Integer, default=5)
    completed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
```

**API:**
- GET /api/quests: 퀘스트 목록
- POST /api/quests/{id}/progress: 진행도 업데이트
- POST /api/quests/{id}/complete: 퀘스트 완료 및 보상

**UI:**
```
frontend/src/components/QuestPanel.js
- 일일 퀘스트 목록
- 진행도 바
- 완료 버튼 및 보상 표시
- 퀘스트 타입별 필터
```

---

#### Day 7-10: LoRA 파인튜닝 준비
**목표:** 사용자 데이터 기반 AI 개인화

**Day 7-8: 데이터 수집**
```
backend/training/data_collector.py
- UserMemory 테이블에서 데이터 추출
- 대화, 일정, 이메일 정보 포함
- JSONL 형식으로 변환
```

**Day 9-10: 파인튜닝 파이프라인**
```
backend/training/lora_finetune.py
- Ollama LoRA 파인튜닝 스크립트
- 하이퍼파라미터 설정 (learning_rate, epochs)
- 평가 스크립트 (training/evaluate.py)
```

**데이터 포맷:**
```json
{
  "messages": [
    {"role": "user", "content": "내일 회의 시간은?"},
    {"role": "assistant", "content": "내일 10시에 회의가 있습니다..."}
  ]
}
```

---

## 📦 필수 의존성 추가

```bash
pip install langchain==0.1.13
pip install langchain-community==0.0.19
pip install chromadb==0.4.24
pip install google-auth-oauthlib==1.2.0
pip install google-auth-httplib2==0.2.0
pip install google-api-python-client==2.105.0
```

---

## 🔗 GitHub 저장소

**저장소:** https://github.com/wkupq/Plan-quest-UI.git

**최신 커밋:**
```
Week 2 Day 8-10: AI 채팅 스트리밍 + Ollama 매니저 + Graceful Shutdown
- backend/routers/chat.py (SSE 스트리밍)
- backend/ollama_manager.py (자동 관리)
- main.py (Graceful Shutdown)
- .gitignore 추가
```

---

## 💡 주의사항

1. **모델 선택:** Ollama에서 llama3.2 → Qwen2.5로 변경
   ```bash
   ollama pull qwen2.5  # Day 1에 실행
   ```

2. **API 키 설정:**
   - Google Calendar: https://console.cloud.google.com
   - Gmail: OAuth2 설정 필요

3. **로컬 개발:**
   ```bash
   cd backend && python main.py
   cd ../frontend && npm start
   ```

4. **데이터베이스:**
   - 현재: habit_forest.db (SQLite)
   - UserMemory 테이블 추가 시 마이그레이션 필요

---

## ✅ 최종 목표 (Week 3-4 완료 후)

```
Week 1-2: 게임 UI + 기본 채팅 ✅
Week 3:   AI 에이전트 + 메모리 + API 연동 ✅
Week 4:   게임 완성 + LoRA 준비 ✅

→ "진정한 개인화된 AI 비서 시스템" 완성!
```

---

**다음 단계:** Week 3 Day 1: agent_core.py 작성 시작
