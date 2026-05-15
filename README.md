# 🌱 PlanQuest — AI 개인 스케줄러

> 로컬 AI(Ollama)와 게임 요소를 결합한 개인 일정 관리 시스템  
> Google Calendar / Gmail 연동 · 습관 추적 · 아이소메트릭 맵 게임

---

## 📌 프로젝트 개요

PlanQuest는 완전 로컬에서 실행되는 AI 스케줄러입니다.  
외부 서버 없이 내 컴퓨터에서만 동작하며, 일정과 습관을 관리하면서 게임처럼 캐릭터를 키울 수 있습니다.

---

## 🏗️ 시스템 구조

```
PlanQuest/
├── ui/
│   ├── backend/          # FastAPI 백엔드 (포트 8000)
│   │   ├── main.py
│   │   ├── models.py     # SQLAlchemy DB 모델
│   │   ├── schemas.py
│   │   ├── database.py
│   │   ├── seed_data.py
│   │   └── routers/
│   │       ├── chat.py       # AI 챗봇 (RAG + Google 컨텍스트)
│   │       ├── habits.py     # 습관 CRUD
│   │       ├── trees.py      # 나무 성장 / 수확
│   │       ├── shop.py       # 상점
│   │       ├── placement.py  # 아이템 배치
│   │       └── user.py       # 유저 프로필
│   └── frontend/         # React 프론트엔드 (포트 3000)
│       └── src/
│           ├── App.js
│           ├── api.js
│           └── components/
│               ├── ChatDashboard.js   # AI 채팅 (스트리밍)
│               ├── IsometricMap.js    # 아이소메트릭 맵
│               ├── HabitPanel.js      # 습관 관리
│               ├── CalendarPanel.js   # 캘린더
│               ├── ShopPanel.js       # 상점
│               ├── InventoryPanel.js  # 인벤토리
│               └── OllamaPopup.js     # Ollama 설치 안내
└── project-files/        # AI 백엔드 (포트 8001)
    ├── rag_chain.py       # RAGChain (ChromaDB + BM25 + RRF)
    ├── auth_manager.py    # Google OAuth 2.0 (keyring 저장)
    ├── gmail_sync.py      # Gmail 증분 동기화
    ├── memory.py          # TTL 기반 메모리 시스템
    ├── scheduler.py       # APScheduler 백그라운드 작업
    ├── security.py        # 프롬프트 인젝션 방어 / 입력 검증
    ├── masking.py         # 민감정보 마스킹
    └── notifier.py        # 크로스플랫폼 알림
```

---

## ⚙️ 주요 기능

### 🤖 AI 스케줄러
- **로컬 LLM**: Ollama + Qwen2.5 14B 기반
- **RAG 파이프라인**: ChromaDB(밀집) + BM25(희소) + RRF 병합 + bge-reranker
- **컨텍스트 주입**: DB 습관/일정 + Google Calendar + Gmail 데이터를 AI에 자동 주입
- **스트리밍 응답**: SSE 방식으로 실시간 토큰 출력

### 📅 Google 연동
- **Google Calendar**: OAuth 2.0 인증, 7일치 일정 조회
- **Gmail**: historyId 기반 증분 동기화 (중복 없음)
- **토큰 보안**: keyring으로 OS 보안 저장소에 암호화 저장

### 🌱 게임 시스템
- **습관 완료 → 하트 획득 → 레벨업**
- **나무 성장**: 습관 완료 시 씨앗 → 새싹 → 작은나무 → 큰나무
- **아이소메트릭 맵**: 구매한 아이템을 맵에 자유롭게 배치
- **상점**: 동물·나무·건물 아이템 (common ~ legendary)

### 🔒 보안
- 프롬프트 인젝션 방어 (`security.py`)
- 외부 데이터 샌드박싱 (`<external_content>` 태그 분리)
- 민감정보 자동 마스킹 (카드번호·주민번호·전화번호)

---

## 🚀 실행 방법

### 사전 준비
- Python 3.10+
- Node.js 18+
- [Ollama](https://ollama.ai) 설치 후 모델 다운로드

```bash
ollama pull qwen2.5:14b
```

### 터미널 1 — UI 백엔드
```bash
cd ui/backend
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### 터미널 2 — 프론트엔드
```bash
cd ui/frontend
npm install
npm start
```

### 터미널 3 — AI 백엔드
```bash
cd project-files
..\.venv\Scripts\activate
python rag_pipeline.py
```

---

## 🔑 Google 연동 설정

1. [Google Cloud Console](https://console.cloud.google.com)에서 OAuth 2.0 클라이언트 ID 생성
2. `project-files/client_secret.json` 저장
3. 첫 실행 시 브라우저에서 Google 계정 인증

---

## 🗂️ 브랜치

| 브랜치 | 내용 |
|--------|------|
| `main` | 통합 메인 코드 |
| `teamc` | TeamC 기여 코드 (메모리·스케줄러·보안) |
| `teamd` | TeamD 기여 코드 (UI·프론트엔드) |

---

## 🛠️ 기술 스택

| 분류 | 기술 |
|------|------|
| AI/LLM | Ollama, Qwen2.5 14B, LangChain |
| RAG | ChromaDB, BM25, bge-reranker |
| 백엔드 | FastAPI, SQLAlchemy, SQLite |
| 프론트엔드 | React, Axios |
| Google API | Calendar v3, Gmail v1, OAuth 2.0 |
| 보안 | keyring, APScheduler |
