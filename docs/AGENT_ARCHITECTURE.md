# Plan-Quest AI Agent 아키텍처

## 🏗️ 전체 시스템 구조

```
┌─────────────────────────────────────────────────────────────┐
│                      React Frontend (클라이언트)               │
│                  ChatDashboard Component                      │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ HTTP POST /api/chat/stream
                         │ {"message": "사용자 쿼리"}
                         │
┌────────────────────────▼────────────────────────────────────┐
│                   FastAPI Backend (서버)                      │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐  │
│  │          routers/chat.py                              │  │
│  │  • /api/chat/stream (POST) - ReAct 스트리밍         │  │
│  │  • /api/chat/tools (GET) - 도구 목록 조회           │  │
│  └────────────────────┬─────────────────────────────────┘  │
│                       │                                       │
│                       ▼                                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │      agent_core.py: PlanQuestAgent                    │  │
│  │                                                        │  │
│  │  ┌─────────────────────────────────────────────┐    │  │
│  │  │  LangChain + Ollama (Qwen2.5)               │    │  │
│  │  │  ReAct Pattern (Reasoning + Acting)         │    │  │
│  │  │  • max_iterations: 10                       │    │  │
│  │  │  • early_stopping: enabled                  │    │  │
│  │  └─────────────────────────────────────────────┘    │  │
│  │                                                        │  │
│  │  Tool Selection & Execution Engine:                  │  │
│  │  사용자 쿼리 분석 → 필요한 도구 선택 → 순차 실행    │  │
│  └────────────┬───────────────────────────────────────┘  │
│               │                                            │
│    ┌──────────┴──────────┬─────────────┬───────────┐    │
│    │                     │             │           │    │
│    ▼                     ▼             ▼           ▼    │
│  ┌──────┐  ┌──────────┐  ┌──────────┐  ┌────────┐     │
│  │Habit │  │Calendar  │  │  Email   │  │Memory  │     │
│  │Tools │  │ Tools    │  │  Tools   │  │Engine  │     │
│  └──────┘  └──────────┘  └──────────┘  └────────┘     │
│    │            │             │           │             │
│    ▼            ▼             ▼           ▼             │
│  ┌────────────────────────────────────────────────┐    │
│  │         Database (SQLite/ChromaDB)              │    │
│  │  • UserProfile, Habit, ShopItem                │    │
│  │  • OwnedItem, PlacedItem, TreeOnMap           │    │
│  │  • UserMemory (Week 3 Day 4-6)                │    │
│  └────────────────────────────────────────────────┘    │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

---

## 🛠️ Tool 계층 구조

```
tools/
├── __init__.py
│
├── habit_tools.py
│   ├── get_habits(user_id)
│   │   └─→ DB에서 모든 습관 조회
│   ├── create_habit(title, repeat_days, times)
│   │   └─→ 새 습관 생성
│   └── complete_habit(habit_id)
│       └─→ 습관 완료 처리 (스트릭, 하트)
│
├── calendar_tools.py
│   ├── search_calendar(query)
│   │   └─→ 일정 검색 ("내일", "회의" 등)
│   ├── get_today_schedule()
│   │   └─→ 오늘 전체 일정
│   └── get_next_events(days)
│       └─→ 향후 N일 일정
│
└── email_tools.py
    ├── search_emails(query)
    │   └─→ 이메일 검색
    ├── get_important_emails()
    │   └─→ 중요 이메일 필터링
    └── classify_emails()
        └─→ 카테고리별 분류
```

---

## 🔄 ReAct 패턴 실행 흐름

```
Step 1: 쿼리 분석 (Reasoning)
┌─────────────────────────────────────────┐
│ 사용자: "내일 회의 있고, 중요한 메일     │
│         있으면 알려줘"                   │
└──────────────┬──────────────────────────┘
               │
               ▼
       [에이전트 분석]
       "이 쿼리는 2개 작업 필요:
        1. 내일 일정 조회
        2. 중요 이메일 조회"
               │
               ▼
Step 2: 도구 선택 (Acting)
┌──────────────────────────────────────────┐
│ 선택된 도구:                              │
│ • search_calendar("내일")                 │
│ • get_important_emails()                  │
└──────────────┬───────────────────────────┘
               │
        ┌──────┴──────┐
        │             │
        ▼             ▼
   [Tool 1]      [Tool 2]
   캘린더        이메일
   일정 반환      정보 반환
        │             │
        └──────┬──────┘
               │
               ▼
Step 3: 결과 통합 (Reasoning)
┌────────────────────────────────────────┐
│ 수집된 정보:                            │
│ • 내일 10:00 팀 미팅                    │
│ • 내일 14:30 프로젝트 리뷰              │
│ • 보스님 Q1 리뷰 요청 메일             │
│ • 클라이언트 계약 검토 긴급 메일       │
└─────────────┬──────────────────────────┘
              │
              ▼
   [최종 응답 생성]
   "내일 일정:
    • 10시 팀 미팅
    • 14시 30분 프로젝트 리뷰
    
    중요 메일:
    • 보스님: Q1 리뷰 요청
    • 클라이언트: 계약 검토 긴급"
              │
              ▼
Step 4: 사용자에게 응답
┌────────────────────────────────────────┐
│ 클라이언트에 SSE 스트리밍 전달          │
│ (문자 단위로 실시간 전송)               │
└────────────────────────────────────────┘
```

---

## 🎯 기능별 도구 매핑

### 사용자 쿼리 → 도구 선택 예시

| 사용자 쿼리 | 활성화 도구 | 응답 |
|-----------|-----------|------|
| "내 습관이 뭐야?" | `get_habits()` | 등록된 모든 습관 |
| "매일 6시 명상 추가" | `create_habit()` | 습관 생성 완료 |
| "운동 끝났어" | `complete_habit()` | 스트릭 증가, 하트 획득 |
| "내일 일정?" | `search_calendar()` | 내일 일정 |
| "오늘 뭐 해야 돼?" | `get_today_schedule()` | 오늘 전체 일정 |
| "주간 일정 보여줘" | `get_next_events(7)` | 7일간 주요 일정 |
| "중요한 메일?" | `get_important_emails()` | 우선순위 높은 이메일 |
| "이메일 분류해" | `classify_emails()` | 카테고리별 분류 |
| **다중 쿼리:** "내일 회의 있고, 중요한 메일 있으면 알려줘" | `search_calendar()` + `get_important_emails()` | 두 정보 통합 응답 |

---

## 💾 데이터 흐름

### Habit Tool 데이터 흐름
```
사용자 쿼리
   │
   ▼
"운동 완료했어" 
   │
   ▼
complete_habit() 
   │
   ├─→ DB에서 관련 Habit 검색
   │
   ├─→ Habit 테이블 수정
   │   • completed_today = True
   │   • streak += 1
   │
   ├─→ UserProfile 테이블 수정
   │   • hearts += habit.hearts_reward
   │   • total_hearts_earned += reward
   │
   └─→ "✅ 운동 완료! (+💗, 연속: 5일)"
```

### Multi-Tool 데이터 흐름
```
쿼리: "내일 회의 있고, 중요한 메일 있으면 알려줘"
   │
   ▼
┌─────────────────────────────┐
│  Tool 1: search_calendar()  │ Tool 2: get_important_emails()
│  ↓                          │ ↓
│  더미 데이터:               │ 더미 데이터:
│  • 10:00 팀 미팅           │ • 보스님 Q1 리뷰
│  • 14:30 프로젝트          │ • 클라이언트 긴급
└─────────────────────────────┘
   │
   ▼
[결과 통합]
   │
   ▼
최종 응답 (SSE 스트리밍)
```

---

## 🔧 설정 값

### agent_core.py 주요 설정
```python
PlanQuestAgent(
    model="qwen2.5:latest",           # Ollama 모델
    base_url="http://127.0.0.1:11434" # Ollama API URL
)

agent = initialize_agent(
    tools=self.tools,                 # 7개 Tool
    llm=llm,                          # Qwen2.5 LLM
    agent=AgentType.REACT_DOCSTRING,  # ReAct 패턴
    verbose=True,                     # 로그 출력
    max_iterations=10,                # 최대 10번 반복
    early_stopping_method="generate", # 조기 종료
    handle_parsing_errors=True        # 파싱 에러 처리
)
```

### 온도 설정 (Creativity vs Consistency)
```python
temperature=0.7  # 중간 (기본)
top_p=0.9        # 높음 (다양성)
top_k=40         # 높음 (탐색)

→ 창의적이면서도 일관성 있는 응답
```

---

## 📊 성능 특성

| 항목 | 값 | 설명 |
|------|-----|------|
| 모델 | Qwen2.5 | 한국어 최적화, 추론 능력 우수 |
| 도구 | 9개 | habit(3) + calendar(3) + email(3) |
| 최대 반복 | 10회 | 무한 루프 방지 |
| 온도 | 0.7 | 창의성과 일관성 균형 |
| 응답 방식 | SSE 스트리밍 | 실시간 문자 단위 전송 |
| 바이어스 | 낮음 | 도구 선택 자유도 높음 |

---

## 🚀 배포 체크리스트

- [x] agent_core.py 구현
- [x] tools 패키지 구현
- [x] routers/chat.py 통합
- [x] 문법 검사 통과
- [ ] pip install 실행
- [ ] Ollama 모델 다운로드
- [ ] 테스트 실행
- [ ] 버그 수정
- [ ] Git 커밋

---

**다음 주제:** Week 3 Day 4-6 - RAG 메모리 파이프라인 (ChromaDB)
