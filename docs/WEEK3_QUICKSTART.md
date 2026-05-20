# ⚡ Week 3 Day 1-3 Quick Start Guide

## 📍 현재 상태
✅ **AI 에이전트 코어 구축 완료**
- LangChain ReAct 패턴 에이전트 구현
- 9개 도구 (Habit, Calendar, Email) 통합
- Qwen2.5 모델 기반 다단계 추론

---

## 🚀 30초 시작 가이드

### 1️⃣ 설치 (첫 번째만)
```bash
cd backend
pip install -r requirements.txt
ollama pull qwen2.5:latest
```

### 2️⃣ 실행
```bash
# Terminal 1: Ollama 서버
ollama serve

# Terminal 2: 백엔드
python main.py

# Terminal 3: 테스트 (선택)
curl -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "내일 회의 있고, 중요한 메일 있으면 알려줘"}'
```

### 3️⃣ 프론트엔드 (기존)
```bash
cd frontend
npm start
```

---

## 🎯 테스트 커맨드

### 에이전트 도구 목록 조회
```bash
curl http://localhost:8000/api/chat/tools | json_pp
```

**응답 예시:**
```json
{
  "available_tools": [
    {
      "name": "get_habits",
      "description": "사용자의 모든 습관과 일정 목록을 조회합니다..."
    },
    ...
  ],
  "total_tools": 9,
  "model": "qwen2.5:latest"
}
```

### 스트리밍 채팅 테스트
```bash
curl -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "오늘 뭐 할 일이 있어?"}'
```

**응답 형식:**
```
data: {"token": "오"}
data: {"token": "늘"}
data: {"token": "은"}
...
data: {"done": true}
```

---

## 📝 주요 변경사항

### ❌ 제거된 것
- 단순 스트리밍 (단일 LLM 호출)
- llama3.2 모델

### ✅ 추가된 것
- ReAct 에이전트 (다단계 추론)
- 9개 Tool (자동 도구 선택)
- Qwen2.5 모델 (향상된 한국어)
- `/api/chat/tools` 엔드포인트

### 🔧 수정된 것
- `routers/chat.py`: 에이전트 통합
- `requirements.txt`: langchain 의존성 추가

---

## 💡 사용 사례

### 사례 1: 일정 + 이메일
**사용자:** "내일 회의 있고, 중요한 메일 있으면 알려줘"
```
[에이전트 분석]
- Task 1: search_calendar("내일")
- Task 2: get_important_emails()

[실행 결과]
AI: "내일 10시 팀 미팅이 있고,
     보스님으로부터 Q1 리뷰 요청 메일이 있습니다."
```

### 사례 2: 습관 생성 + 조회
**사용자:** "매일 아침 6시 명상 추가하고, 내 습관 보여줘"
```
[에이전트 분석]
- Task 1: create_habit("명상", times=["06:00"])
- Task 2: get_habits()

[실행 결과]
AI: "✅ 명상 습관이 생성되었습니다.
     현재 습관:
     - 명상: 월~금 / 06:00
     - 운동: 월,수,금 / 18:00
     ..."
```

### 사례 3: 습관 완료 + 피드백
**사용자:** "아침 운동 완료했어"
```
[에이전트 분석]
- Task: complete_habit("운동")

[실행 결과]
AI: "✅ 운동 완료! (+💗, 연속: 5일)
     계속 화이팅! 🎉"
```

---

## 📂 파일 구조

```
backend/
├── agent_core.py                 # ⭐ ReAct 에이전트 코어
├── routers/
│   ├── chat.py                   # (수정) 에이전트 통합
│   └── ...
├── tools/                         # ⭐ 도구 패키지
│   ├── __init__.py
│   ├── habit_tools.py            # 습관 도구
│   ├── calendar_tools.py         # 캘린더 도구
│   └── email_tools.py            # 이메일 도구
├── models.py
├── database.py
├── main.py
├── requirements.txt              # (수정) 의존성 추가
└── ...
```

---

## 🔍 디버깅

### 문제: "에이전트가 초기화되지 않았습니다"
```
❌ 에이전트가 초기화되지 않았습니다. Ollama를 실행해주세요.
```
**해결:** Ollama 서버가 실행 중이어야 합니다.
```bash
ollama serve
```

### 문제: "모델을 찾을 수 없습니다"
```
❌ Error: Model 'qwen2.5:latest' not found
```
**해결:** 모델을 다운로드해야 합니다.
```bash
ollama pull qwen2.5:latest
```

### 문제: LangChain 임포트 에러
```
ModuleNotFoundError: No module named 'langchain'
```
**해결:** 의존성을 설치합니다.
```bash
pip install -r requirements.txt
```

---

## 📊 성능 팁

### 속도 개선
1. **로컬 테스트 (개발)**
   - Qwen2.5 (추천: 빠르고 한국어 최적)
   
2. **정확도 개선**
   - 시스템 프롬프트 최적화
   - Tool description 명확화
   - max_iterations 조정

### 메모리 최적화
1. 도구 실행 후 캐싱
2. 오래된 대화 정리 (Day 4-6에서 구현)
3. ChromaDB 메모리 압축 (Day 4-6)

---

## ✅ 체크리스트 (설치 후)

- [ ] `pip install -r requirements.txt` 완료
- [ ] `ollama pull qwen2.5:latest` 완료
- [ ] `python main.py` 실행 (에러 없음)
- [ ] `curl http://localhost:8000/api/chat/tools` 응답 확인
- [ ] 채팅 테스트 (스트리밍 정상)
- [ ] 도구 자동 선택 확인 (여러 도구 사용 쿼리)

---

## 📖 다음 단계

### Week 3 Day 4-6: RAG 메모리
- ChromaDB 벡터 저장소
- 과거 대화 학습
- 자동 메모리 정리

**파일:** `WEEK3_ROADMAP.md` → Week 3 Day 4-6 섹션

### 문서
- **아키텍처:** `AGENT_ARCHITECTURE.md`
- **상세:** `WEEK3_DAY1-3_SUMMARY.md`
- **전체 계획:** `WEEK3_ROADMAP.md`

---

## 🎓 학습 포인트

### ReAct 패턴이란?
- **R**easoning: 문제 분석
- **A**cting: 도구 실행
- 반복적으로 최적 답 도출

### Ollama + LangChain의 장점
✅ 로컬 실행 (개인정보 보호)  
✅ 오프라인 사용 가능  
✅ 자유로운 커스터마이징  
✅ 비용 절감  

---

**🚀 Ready to go!**  
문제 발생 시: `WEEK3_DAY1-3_SUMMARY.md` 참고

