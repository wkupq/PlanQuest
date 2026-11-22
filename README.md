# PlanQuest

**완전 로컬 AI 개인 스케줄러** — 온디바이스 LLM 기반 자연어 일정 등록 · Gmail 연동 · 게임화 습관 관리

> 외부 클라우드 없이 Qwen2.5 7B 모델을 로컬에서 구동하여 사용자 데이터를 디바이스 밖으로 내보내지 않는 AI 비서 앱입니다.  
> 경쟁 앱(Habitica · Open Claw · 습관의 숲)이 각각 하나씩 구현한 **로컬 AI · 게임화 · 자연어 인터페이스**를 단일 프로젝트에서 동시 구현합니다.

---

## 시스템 아키텍처

![PlanQuest 시스템 아키텍처](docs/architecture.png)

| 레이어 | 구성 요소 |
|--------|-----------|
| 프론트엔드 | React 18 — 자연어 채팅 UI · 일정 관리 · 루틴 트래킹 · 상점 |
| 백엔드 | FastAPI · chat.py 파이프라인 (`__CREATE__` 태그 파싱 → SQLite) · 프롬프트 보안 |
| AI 엔진 | Ollama (Qwen2.5 7B 온디바이스) · 하이브리드 RAG · LoRA 데이터 파이프라인 |
| 데이터 | SQLite DB · ChromaDB (벡터 임베딩) · TTL 기반 메모리 캐시 |
| 외부 연동 | Gmail API · Google Calendar API (OAuth2 · APScheduler 30분 주기 동기화) |

---

## 핵심 기술

### 자연어 → DB 등록 파이프라인

사용자가 "내일 오전 7시 운동 추가해줘"라고 입력하면:

1. `_CREATE_INTENT_KEYWORDS` 기반 의도 분류
2. LLM이 응답 마지막에 `__CREATE__ {"title":"운동","time":"07:00",...}` 자동 삽입
3. 백엔드 정규식 파서 → 필드 추출 → SQLite 저장
4. 필드 누락 시 AI가 사용자에게 되묻는 fallback 로직 실행

단순 챗봇이 아니라 대화 한 문장이 실제 DB 레코드 생성으로 직결됩니다.

### 프롬프트 보안 — 태그 격리

Gmail 본문 등 외부 데이터를 `<EXTERNAL_DATA>...</EXTERNAL_DATA>` 태그로 감싸 시스템 프롬프트와 분리합니다.  
Gmail 컨텍스트는 **최근 수신 메일** · **키워드 검색 결과** 두 섹션으로 주입해 AI 혼동 오류를 차단합니다.

```python
# chat.py — 외부 데이터 격리 예시
context = f"""<EXTERNAL_DATA>
[최근 메일]
{recent_mail_context}

[키워드 검색 결과]
{keyword_search_context}
</EXTERNAL_DATA>"""
```

### 하이브리드 RAG (Dense + Sparse + RRF)

로컬 7B 모델은 벡터 검색만으로 'SKALA', 'SKCT' 같은 고유명사 매칭이 취약합니다.

```
ChromaDB (Dense)  ──┐
                    ├── RRF 병합 ──▶ CrossEncoder 재순위 ──▶ LLM
BM25 (Sparse)     ──┘
```

- **RRF (Reciprocal Rank Fusion)**: 각 검색 결과 순위에 역수를 취해 합산 → 점수 스케일 무관 공정 병합
- **CrossEncoder 재순위**: 최종 관련 컨텍스트만 LLM에 전달
- HMAC-SHA256으로 BM25 인덱스 무결성 검증

### LoRA 학습 데이터 파이프라인

앱 사용 중 쌓이는 대화 로그를 Alpaca 포맷 JSON으로 자동 변환합니다.  
Qwen 모델 온디바이스 파인튜닝 인프라를 선제적으로 구축해 두었으며, 실제 학습은 GPU 리소스 확보 후 적용 예정입니다.

```bash
python project-files/data_pipeline.py export
# → lora_data/processed/alpaca_train.json
```

---

## 기술 스택

| 분류 | 기술 |
|------|------|
| 백엔드 | Python 3.11 · FastAPI · Uvicorn · SQLite · APScheduler |
| AI | Ollama · Qwen2.5 7B · ChromaDB · BM25 (rank-bm25) · sentence-transformers |
| 보안 | HMAC-SHA256 · 정규식 마스킹 (이메일 · 전화번호 · 카드번호) |
| 외부 API | Google Calendar API · Gmail API · OAuth2 |
| 프론트엔드 | React 18 · Axios · SSE 스트리밍 |
| 테스트 | pytest 57개 · 커버리지 70% |

---

## 프로젝트 구조

```
PlanQuest_App/
├── backend/
│   ├── main.py                  # FastAPI 앱 진입점
│   ├── routers/
│   │   ├── chat.py              # __CREATE__ 태그 파싱 · 의도 분류 · 프롬프트 보안
│   │   ├── habits.py            # 루틴 CRUD · 완료 처리 · 하트 포인트
│   │   ├── calendar.py          # 월간 달성률 히트맵
│   │   ├── shop.py              # 캐릭터 상점
│   │   └── user.py              # 사용자 프로필
│   └── models.py / schemas.py / database.py
│
└── project-files/
    ├── rag_pipeline.py          # DenseRetriever · SparseRetriever · RRF · Reranker
    ├── memory.py                # TTL 기반 4영역 메모리 만료
    ├── security.py              # 보안 설계 (태그 격리 · 마스킹)
    ├── masking.py               # 정규식 마스킹 필터
    ├── data_formatter.py        # 대화 로그 → Alpaca 포맷 변환
    ├── lora_trainer.py          # Unsloth/PEFT 기반 LoRA 파인튜닝
    ├── gmail_api.py             # Gmail 탐색 · 날짜 필터 · 키워드 검색
    ├── scheduler.py             # APScheduler Google API 30분 주기 동기화
    └── oauth_sync.py            # OAuth2 토큰 관리
```

---

## 빠른 시작

### 사전 준비

```powershell
# Ollama 설치: https://ollama.com
ollama pull qwen2.5:7b

# 백엔드 의존성
cd PlanQuest_App\backend
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt

# 프론트엔드 의존성
cd PlanQuest_App\frontend
npm install
```

### 실행

```powershell
# 터미널 1 — AI 서버
ollama serve

# 터미널 2 — FastAPI 백엔드
cd PlanQuest_App\backend
uvicorn main:app --reload --host 127.0.0.1 --port 8000

# 터미널 3 — React 프론트엔드
cd PlanQuest_App\frontend
npm start
```

`http://localhost:3000` 접속

---

## 주요 API

```
# 채팅 (SSE 스트리밍)
POST /api/chat/stream

# 습관 관리
GET  /api/habits
POST /api/habits
POST /api/habits/{id}/complete

# 캘린더
GET  /api/calendar/{year}/{month}

# 게임 시스템
GET  /api/shop
POST /api/shop/{id}/buy
GET  /api/placed-items
POST /api/placed-items/{id}/harvest
```

---

## 테스트

```powershell
cd PlanQuest_App\backend
pytest --cov=. --cov-report=term-missing
# 57개 단위 테스트 · 커버리지 70%
```

---

## 팀 구성

| 팀원 | 담당 모듈 |
|------|-----------|
| 이용상 | chat.py 파이프라인 · `__CREATE__` 태그 파싱 · 프롬프트 보안 · LoRA 데이터 파이프라인 · Gmail 연동 |
| 안성현 | 루틴 관리 UI · Google Calendar 연동 · APScheduler · OAuth2 · pytest |
| 손세환 | 하이브리드 RAG (rag_pipeline.py) · ChromaDB · BM25 · 메모리 만료 시스템 |
| (팀원) | 프론트엔드 · 게임 시스템 (아이소메트릭 UI · 캐릭터 · 상점) |

---

## 참고

- [Google API OAuth2 설정 가이드](backend/integrations/README_연동가이드.md)
- GitHub: https://github.com/wkupq/PlanQuest

---

캡스톤 프로젝트 — 학술·비상업 용도  
최종 업데이트: 2026-11
