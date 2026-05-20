# 🎉 Week 6 완료 — Team Member D

**완료일:** 2026-05-13
**테마:** AI 자동화 + 사용자 입력 효율화 + 피드백 루프

W5 까지 (인사이트 + 메모리 + WebSocket) 위에 **사용자 경험 + AI 응답 품질** 강화 레이어.

---

## 📂 W6 새/변경 파일

```
backend/
├── routers/
│   ├── suggestions.py     ★ NEW — AI 자동 일정 추천 엔진
│   └── feedback.py        ★ NEW — AI 응답 평가 + 메모리 저장
├── slash_commands.py      ★ NEW — 챗봇 슬래시 커맨드 (12개)
├── routers/chat.py        (수정) — "/" 시작 메시지 즉시 처리
├── main.py                (수정) — suggestions, feedback 라우터 등록
├── test_d_features.py     (수정) — W6 항목 3개 추가
├── seed_data.py           (수정) — 새 캐릭터 6마리
├── reset_shop.py          (수정) — 새 캐릭터 6마리
└── add_new_chars.py       ★ NEW — 6마리 증분 추가 (wipe 없이)
```

---

## 🆕 신규 API 엔드포인트

### AI 자동 일정 추천 (W6 D1-2)
```
GET /api/suggestions/habits?limit=5
  → 사용자 패턴 + 라이브러리 기반 추천 (Top N)

GET /api/suggestions/empty-slots
  → 시간대별 빈 슬롯 + 조언

GET /api/suggestions/best-time?habit_title=운동
  → 특정 일정의 최적 시간 추천
```

**추천 라이브러리** 4 카테고리 × 다수 일정:
- 건강: 물 마시기, 스트레칭, 운동, 산책
- 공부: 독서, 영어 단어, 강의, 복습
- 마음: 명상, 일기, 감사 적기
- 생활: 정리, 장보기, 이불 개기

**점수 계산**:
- 사용자의 강한 시간대(아침/낮/저녁/밤) 매치 시 +2.0
- 해당 카테고리 일정이 0개면 +1.5 (다양성 보너스)

### AI 응답 피드백 (W6 D4)
```
POST /api/feedback/rate
  body: { rating: "good" | "bad", user_message: ..., ai_response: ... }
  → 메모리 자동 저장 (good=0.8 importance, bad=0.2)

GET  /api/feedback/recent?limit=20
  → 최근 피드백 목록

GET  /api/feedback/stats
  → 만족도 비율, 7일 추세
```

**작동 원리**:
- 👍 피드백 → "[좋아한 응답] Q...A..." 로 high importance 메모리
- 👎 피드백 → "[피해야 할 응답] Q...A..." 로 low importance
- 다음 AI 응답 시 `build_personalization_context()` 가 자동으로 RAG 검색 → 좋은 응답 패턴 참고, 나쁜 응답 회피

---

## 💬 챗봇 슬래시 커맨드 (W6 D3)

`/` 로 시작하는 메시지는 **LLM 없이 즉시 실행** — 빠르고 정확.

| 명령 | 효과 |
|------|------|
| `/help` | 도움말 |
| `/hearts` | 현재 하트 |
| `/summary` | 정원 요약 |
| `/today` | 오늘 진행도 |
| `/list` | 등록된 일정 |
| `/history [week\|month]` | 완료 기록 |
| `/pattern` | 강한/약한 요일·시간 |
| `/stats` | 종합 통계 |
| `/suggest` | AI 추천 일정 |
| `/add <제목>` | 일정 즉시 추가 (라이브러리 매칭 시 기본 시간/요일 자동) |
| `/complete <키워드>` | 일정 완료 처리 (하트 + streak + 나무 성장) |

**구현**:
- `slash_commands.py` 에 12개 핸들러
- `routers/chat.py` 가 메시지 첫 글자 `/` 체크 → `dispatch_command()` → SSE 스트리밍 응답
- Ollama 없어도 100% 동작 (LLM 불필요)

---

## 🐾 W6 캐릭터 추가 (6마리)

기존 8 → **14마리**

| 이미지 | 이름 | 등급 | 가격 |
|--------|------|------|------|
| 🐧 | **불꽃펭귄** | common | 5H |
| 🐹 | **호랑햄스터** | common | 4H |
| 🎧 | **음악수달** | rare | 7H |
| 🌈 | **무지개여우** | **unique** | 10H |
| ⭐ | **별자리양** | **unique** | 12H |
| 💜 | **라벤더냥** | rare | 6H |

총 14마리 분포: common 8 / rare 3 / **unique 3**

---

## 🚀 사용자 실행

```powershell
cd C:\Users\guswl\OneDrive\Desktop\Plan-quest\backend

# 신규 캐릭터 6마리 DB 추가 (기존 보유는 유지)
python add_new_chars.py

# 통합 검증 (13개 항목)
python test_d_features.py

# 백엔드 실행
python main.py
```

### API 빠른 테스트

```powershell
# 자동 일정 추천
curl http://localhost:8000/api/suggestions/habits

# 빈 시간대
curl http://localhost:8000/api/suggestions/empty-slots

# 슬래시 커맨드 (POST chat/stream 으로)
curl -X POST "http://localhost:8000/api/chat/stream" `
  -H "Content-Type: application/json" `
  -d '{\"message\":\"/help\"}'

# 피드백 평가
curl -X POST http://localhost:8000/api/feedback/rate `
  -H "Content-Type: application/json" `
  -d '{\"rating\":\"good\",\"user_message\":\"하트?\",\"ai_response\":\"5개\"}'
```

---

## 📊 D 역할 누적 (W3 → W6)

| 주차 | 핵심 |
|------|------|
| W3 D1-3 | LangChain ReAct 에이전트 + 9 기본 도구 |
| W3 D4-6 | RAG 메모리 (ChromaDB) |
| W3 D7-10 | Google Calendar/Gmail 스캐폴드 |
| W4 D1-3 | 게임 상태 인식 도구 6 추가 (총 15) |
| W4 D4-6 | 능동 추천 + 패턴 분석 |
| W4 D7-10 | 캘린더 히트맵 + 완료 기록 도구 (총 18 도구) |
| W5 D1-2 | AI 인사이트 리포트 (LLM) |
| W5 D3 | 메모리 자동 카테고리화 |
| W5 D4 | WebSocket 실시간 알림 |
| W5 D5 | 통합 + 문서 |
| **W6 D1-2** | **자동 일정 추천 + 빈 슬롯 + 최적 시간** |
| **W6 D3** | **챗봇 슬래시 커맨드 12개** |
| **W6 D4** | **AI 응답 피드백 시스템** |
| **W6 D5** | **통합 + 문서 (13/13 검증)** |

---

## 🤝 협업 인터페이스 (W6 신규)

| 팀 | API | 용도 |
|----|-----|------|
| 프론트 (일정 패널) | `GET /api/suggestions/habits` | 추천 일정 카드 표시 |
| 프론트 (대시보드) | `GET /api/suggestions/empty-slots` | 시간대 분석 시각화 |
| 프론트 (채팅) | `/` 시작 메시지 | 즉시 응답 (LLM 우회) |
| 프론트 (채팅) | `POST /api/feedback/rate` | AI 응답 옆 👍/👎 버튼 |

---

## 🎯 W7+ 다음 단계 후보

- **음성 I/O** — TTS/STT (Coqui/Whisper)
- **OAuth 실제 연동** — Google Calendar/Gmail credentials.json 적용
- **다국어 지원** — i18n
- **모델 파인튜닝** — 누적된 피드백 데이터로 LoRA
- **사용자 통계 export** — PDF/Excel 리포트

---

이상 D 역할 W6 완료. W3-W6 통틀어 19일치 핵심 백엔드 + 자동화 작업.
