# Week 3 Day 1-3: AI 에이전트 코어 구축 ✅ 완료

**작성일:** 2026-05-01  
**구현 상태:** Ready for Testing  
**Next Step:** pip install + 테스트

---

## 📋 구현된 파일

### 1. **backend/tools/__init__.py** ✅
- 도구 패키지 초기화
- 모든 도구 함수 import/export

### 2. **backend/tools/habit_tools.py** ✅
**기능:**
- `get_habits()` - 등록된 모든 습관/일정 조회
- `create_habit()` - 새 습관 생성 (제목, 반복 요일, 시간, 보상)
- `complete_habit()` - 습관 완료 처리 (스트릭 증가, 하트 획득)

**데이터베이스 연동:**
- SQLAlchemy ORM을 통해 Habit, UserProfile 테이블 조작
- 자동 트랜잭션 처리 및 에러 핸들링

### 3. **backend/tools/calendar_tools.py** ✅
**기능:**
- `search_calendar()` - 캘린더 일정 검색 (내일, 다음주 등)
- `get_today_schedule()` - 오늘 전체 일정 조회
- `get_next_events()` - 향후 N일 주요 일정 조회

**현재 상태:**
- 더미 데이터로 구현 (Google Calendar API는 Week 3 Day 7-8)

### 4. **backend/tools/email_tools.py** ✅
**기능:**
- `search_emails()` - 이메일 검색
- `get_important_emails()` - 중요 이메일 필터링
- `classify_emails()` - 카테고리별 자동 분류

**현재 상태:**
- 더미 데이터로 구현 (Gmail API는 Week 3 Day 9-10)

### 5. **backend/agent_core.py** ✅
**핵심 기능:**
- `PlanQuestAgent` 클래스
  - LangChain + Ollama 통합
  - ReAct (Reasoning + Acting) 패턴
  - 최대 10 iterations, early stopping
  - 7개 도구 자동 선택

- `get_agent()` - 전역 에이전트 인스턴스
- `reset_agent()` - 에이전트 리셋
- `test_agent()` - 테스트 코드 포함

**도구 목록 (7개):**
1. get_habits - 습관 조회
2. create_habit - 습관 생성
3. complete_habit - 습관 완료
4. search_calendar - 캘린더 검색
5. get_today_schedule - 오늘 일정
6. get_next_events - 향후 일정
7. search_emails - 이메일 검색
8. get_important_emails - 중요 이메일
9. classify_emails - 이메일 분류

### 6. **backend/routers/chat.py** ✅ (수정)
**변경 사항:**
- 기존 단순 스트리밍 → ReAct 에이전트로 변경
- `/api/chat/stream` - 에이전트 기반 응답
- `/api/chat/tools` - NEW: 사용 가능한 도구 목록 API

**모델 변경:**
- `llama3.2:latest` → `qwen2.5:latest` (향상된 추론)

### 7. **backend/requirements.txt** ✅ (수정)
**추가 의존성:**
```
langchain==0.1.13
langchain-community==0.0.19
chromadb==0.4.24
google-auth-oauthlib==1.2.0
google-auth-httplib2==0.2.0
google-api-python-client==2.105.0
```

---

## 🛠️ 설치 및 실행 방법

### Step 1: 의존성 설치
```bash
cd backend
pip install -r requirements.txt
```

### Step 2: 모델 다운로드 (처음 한 번)
```bash
ollama pull qwen2.5:latest
```

### Step 3: 백엔드 실행
```bash
python main.py
```

### Step 4: 테스트
```bash
curl -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "내일 회의 있고, 중요한 메일 있으면 알려줘"}'
```

---

## 🧪 테스트 시나리오

### 테스트 1: 일정 조회
**쿼리:** "내일 일정이 뭐야?"
**기대 응답:** 에이전트가 `search_calendar()` 도구를 호출해 일정 반환

### 테스트 2: 다중 도구 사용
**쿼리:** "내일 회의 있고, 중요한 메일 있으면 알려줘"
**기대 응답:** 에이전트가 `search_calendar()` + `get_important_emails()` 자동 호출

### 테스트 3: 습관 생성
**쿼리:** "매일 아침 6시 명상 습관 추가해"
**기대 응답:** 에이전트가 `create_habit()` 호출해 습관 생성

### 테스트 4: 습관 완료
**쿼리:** "아침 운동 완료했어"
**기대 응답:** 에이전트가 관련 습관을 찾아 `complete_habit()` 호출

### 테스트 5: 도구 목록
**엔드포인트:** GET `/api/chat/tools`
**응답:** 사용 가능한 7개 도구의 이름과 설명

---

## 🔄 ReAct 패턴 동작 원리

```
사용자 쿼리
    ↓
[1단계] 쿼리 분석 (ReAct)
    - "내일 회의 있고, 중요한 메일 있으면 알려줘"
    - 필요한 도구: search_calendar, get_important_emails
    ↓
[2단계] 도구 선택 및 실행
    - search_calendar() 실행 → 일정 반환
    - get_important_emails() 실행 → 이메일 반환
    ↓
[3단계] 결과 통합
    - "내일 10시 팀 미팅이 있고,
      보스님으로부터 Q1 리뷰 요청 메일이 있습니다."
    ↓
사용자에게 응답
```

---

## ✅ 체크리스트

- [x] agent_core.py 구현
- [x] 3개 도구 그룹 구현 (habit, calendar, email)
- [x] ReAct 프롬프트 및 에이전트 구성
- [x] Ollama + LangChain 통합
- [x] routers/chat.py 수정
- [x] /api/chat/tools 엔드포인트 추가
- [x] requirements.txt 업데이트
- [ ] pip install 실행 (다음 단계)
- [ ] 테스트 실행 및 검증 (다음 단계)

---

## 📝 다음 단계 (Day 4-6)

**Week 3 Day 4-6: RAG 메모리 파이프라인**

### 구현할 파일:
1. `backend/memory_engine.py` - ChromaDB 벡터 DB
2. `backend/routers/memory.py` - 메모리 API
3. `backend/models.py` 수정 - UserMemory 테이블 추가

### 주요 기능:
- ChromaDB 벡터 저장소
- OllamaEmbeddings로 임베딩
- 유사도 검색 (top_k=3)
- 메모리 임계값 엔진 (자동 정리)

### 효과:
```
사용자: "지난번에 한 그 프로젝트 어떻게 됐어?"
→ 과거 대화 기록 자동 검색
→ "아, 그 XXX 프로젝트요! 현재 상태는..."
```

---

## 🐛 알려진 제한사항

1. **Calendar & Email 더미 데이터**
   - 실제 Google Calendar API 연동은 Day 7-8
   - 실제 Gmail API 연동은 Day 9-10

2. **모델 성능**
   - Qwen2.5는 한국어 추론 최적화됨
   - llama3.2보다 향상된 다단계 추론 능력

3. **에이전트 반복 제한**
   - max_iterations=10으로 설정
   - 무한 루프 방지

---

**상태:** ✅ Week 3 Day 1-3 완료  
**다음 작업:** requirements.txt 설치 → 테스트 → Day 4-6 시작
