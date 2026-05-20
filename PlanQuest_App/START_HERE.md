# PlanQuest_App — 통합 실행 가이드

> **이 폴더만 사용하세요.** TeamC + TeamD + Team A 최신 파일이 모두 여기에 통합됐습니다.

---

## 폴더 구조

```
PlanQuest_App/
├── backend/          ← FastAPI 서버 (포트 8000)
├── frontend/         ← React 앱 (포트 3000) — TeamD Week 3-6 최신 UI
├── project-files/    ← AI 엔진 (RAG + Ollama + LoRA 데이터)
└── START_HERE.md     ← 이 파일
```

---

## 1. 사전 준비 (최초 1회)

### Ollama 설치 및 모델 다운로드
```powershell
# Ollama 설치: https://ollama.com 에서 다운로드 후 설치
ollama pull qwen2.5:7b
```

### Python 가상환경 (backend)
```powershell
cd PlanQuest_App\backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
pip install requests chromadb rank_bm25 sentence-transformers
```

### Python 가상환경 (project-files)
```powershell
cd PlanQuest_App\project-files
python -m venv venv
venv\Scripts\activate
pip install requests chromadb rank_bm25 sentence-transformers
```

### Node 패키지 (frontend)
```powershell
cd PlanQuest_App\frontend
npm install
```

---

## 2. 서버 실행 (매번)

### 터미널 1 — Ollama AI 서버
```powershell
ollama serve
```

### 터미널 2 — FastAPI 백엔드
```powershell
cd PlanQuest_App\backend
venv\Scripts\activate
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### 터미널 3 — React 프론트엔드
```powershell
cd PlanQuest_App\frontend
npm start
```

브라우저에서 `http://localhost:3000` 접속

---

## 3. 채팅으로 학습 데이터 수집

앱에서 AI 비서에게 말을 걸면 자동으로 학습 데이터가 쌓입니다.

**좋은 질문 예시:**
- "오늘 할 일 정리해줘"
- "이번 주 일정 알려줘"
- "내일 오전에 운동 일정 추가해줘"
- "저번 주에 못한 습관이 뭐야?"
- "영어 공부 매일 30분 루틴 만들어줘"

---

## 4. 학습 데이터 내보내기

```powershell
cd PlanQuest_App\project-files
python data_pipeline.py export
# → lora_data/processed/alpaca_train.json 생성
```

---

## 주의사항

- `project-files/` 파일 수정 후에는 **백엔드 서버를 재시작**해야 반영됩니다 (`--reload`는 backend/ 폴더만 감시)
- DB 파일(`habit_forest.db`)은 `backend/` 폴더에 자동 생성됩니다
- AI 응답이 느린 건 정상 (로컬 모델이라 GPU 없으면 30~60초 소요)
