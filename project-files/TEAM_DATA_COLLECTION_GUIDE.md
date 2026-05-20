# 📚 PlanQuest LoRA 학습 데이터 수집 가이드
> **팀원 모두가 함께 읽고 따라하세요!**  
> 목표: 각자 최소 **100개 이상**의 고품질 대화를 수집 → 팀 전체 500개+ Alpaca JSON 완성

---

## 📋 목차
1. [사전 설치 요건](#1-사전-설치-요건)
2. [프로젝트 클론 및 브랜치 설정](#2-프로젝트-클론-및-브랜치-설정)
3. [Python 가상환경 설정](#3-python-가상환경-설정)
4. [Ollama 설치 및 모델 다운로드](#4-ollama-설치-및-모델-다운로드)
5. [서버 실행 방법 (3개 터미널)](#5-서버-실행-방법-3개-터미널)
6. [좋은 학습 데이터를 위한 채팅 방법](#6-좋은-학습-데이터를-위한-채팅-방법)
7. [Alpaca JSON 추출 방법](#7-alpaca-json-추출-방법)
8. [JSON 파일 공유 방법](#8-json-파일-공유-방법)
9. [자주 묻는 질문 (FAQ)](#9-자주-묻는-질문-faq)

---

## 1. 사전 설치 요건

### ✅ 필수 소프트웨어 (버전 맞춰주세요!)

| 소프트웨어 | 권장 버전 | 다운로드 링크 |
|------------|-----------|--------------|
| **Python** | 3.10 이상 | https://www.python.org/downloads/ |
| **Node.js** | 18 이상 | https://nodejs.org/ |
| **Git** | 최신 | https://git-scm.com/ |
| **Ollama** | 최신 | https://ollama.ai |

### Python 버전 확인
```powershell
python --version
# Python 3.10.x 또는 그 이상이어야 함
```

### Node.js 버전 확인
```powershell
node --version
# v18.x.x 또는 그 이상이어야 함
```

> ⚠️ **주의**: Python 3.9 이하면 호환성 문제가 발생합니다. 반드시 3.10+ 사용!

---

## 2. 프로젝트 클론 및 브랜치 설정

### 이미 클론된 경우 → 최신 코드로 업데이트
```powershell
cd PlanQuest

# index.lock 오류가 나면 먼저 실행
Remove-Item ".git\index.lock" -Force -ErrorAction SilentlyContinue

# 최신 코드 받기
git fetch --all
git checkout main
git pull origin main
```

### 처음 클론하는 경우
```powershell
git clone https://github.com/[팀장 GitHub]/PlanQuest.git
cd PlanQuest
git checkout main
```

---

## 3. Python 가상환경 설정

**두 곳에 각각 가상환경을 만들어야 합니다.**

### 3-1. AI 백엔드 (project-files/) 가상환경

```powershell
cd project-files

# 가상환경 생성
python -m venv venv

# 가상환경 활성화 (PowerShell)
.\venv\Scripts\Activate.ps1

# 활성화 확인: (venv) 표시가 나타나야 함
# (venv) PS C:\...\project-files>

# 패키지 설치 (버전 고정)
pip install -r requirements.txt
```

> ⚠️ **sqlcipher3 설치 오류가 나면:**
> ```powershell
> pip install sqlcipher3-binary
> ```
> Windows에서는 `sqlcipher3` 대신 `sqlcipher3-binary`를 사용해야 합니다.

> ⚠️ **win10toast 설치 오류가 나면 (Mac/Linux):**
> ```bash
> pip install -r requirements.txt --ignore-requires-python
> # 또는 requirements.txt에서 win10toast 줄을 주석 처리 후 설치
> ```

### 3-2. FastAPI 백엔드 (ui/backend/) 가상환경

```powershell
# 새 터미널 열기 (또는 deactivate 후 이동)
cd ..\ui\backend

python -m venv venv
.\venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

### 3-3. React 프론트엔드 패키지 설치

```powershell
cd ..\frontend

npm install
```

---

## 4. Ollama 설치 및 모델 다운로드

### Ollama 설치
1. https://ollama.ai 에서 Windows용 설치 파일 다운로드
2. 설치 완료 후 Ollama가 백그라운드에서 자동 실행됨
3. 확인:
```powershell
ollama list
# 모델 목록이 나오면 정상
```

### Qwen2.5:14b 모델 다운로드
```powershell
ollama pull qwen2.5:14b
```

> ⏱️ **모델 크기: 약 9GB** — 네트워크 속도에 따라 10~30분 소요  
> 다운로드 중에도 다른 설정 작업은 계속할 수 있어요!

> 💡 **용량이 부족하면** 작은 모델도 OK:
> ```powershell
> ollama pull qwen2.5:7b
> ```

---

## 5. 서버 실행 방법 (3개 터미널)

**터미널 3개를 각각 따로 열어서 실행해야 합니다!**

### 🖥️ 터미널 1 — AI 백엔드 서버 (포트 8001)

```powershell
cd project-files
.\venv\Scripts\Activate.ps1
python ai_backend.py
```

정상 실행 확인:
```
INFO:     Uvicorn running on http://0.0.0.0:8001
INFO:     RAGChain 초기화 완료
```

### 🖥️ 터미널 2 — FastAPI 백엔드 서버 (포트 8000)

```powershell
cd ui\backend
.\venv\Scripts\Activate.ps1
uvicorn main:app --reload --port 8000
```

정상 실행 확인:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

### 🖥️ 터미널 3 — React 프론트엔드 (포트 3000)

```powershell
cd ui\frontend
npm start
```

정상 실행 확인:
- 브라우저가 자동으로 `http://localhost:3000` 열림
- PlanQuest 앱 화면이 보이면 성공!

### 🔍 서버 상태 확인
```powershell
# AI 백엔드 정상 여부
curl http://localhost:8001/health

# FastAPI 정상 여부
curl http://localhost:8000/api/chat/health
```

---

## 6. 좋은 학습 데이터를 위한 채팅 방법

> **핵심 원칙**: AI가 "스케줄 관리 전문 비서"처럼 답변하게끔 질문하세요.  
> 애매하거나 짧은 답변이 나오면 → 다시 질문하거나 더 구체적으로 물어보세요.

### ✅ 좋은 질문 예시 (이런 것들을 많이 물어보세요!)

#### 📅 일정 관리 유형
```
- 오늘 해야 할 일이 뭐야?
- 내일 오후에 어떤 일정 있어?
- 이번 주 목요일 비어있어?
- 다음 주 월요일 오전에 미팅 잡아줘
- 오늘 오후 3시부터 5시까지 공부 시간 추가해줘
- 저녁 8시에 운동 습관 추가해줘, 월/수/금 반복으로
- 내일 스터디 일정을 오후 2시로 바꿔줘
```

#### ⏰ 시간 분석 유형
```
- 요즘 공부에 얼마나 시간 쓰고 있어?
- 이번 달에 운동을 몇 번 했어?
- 나 스트릭 며칠째야?
- 어제 완료한 습관이 뭐야?
- 지난 주 가장 많이 한 활동이 뭐야?
```

#### 📊 추천/조언 유형
```
- 오늘 일정이 빡빡한데 어떻게 정리하면 좋을까?
- 집중력 높이는 일정 짜는 법 알려줘
- 공부랑 운동을 균형있게 하려면 어떻게 해야 해?
- 내 습관 중에 우선순위 정해줘
- 스트릭 계속 유지하려면 뭐가 중요해?
```

#### 🎯 목표 설정 유형
```
- 이번 주 목표를 3개만 정해줘
- 매일 30분 독서 습관 만들려면 어떻게 해야 해?
- 자격증 공부 계획 세워줘, 시험이 2달 후야
- 아침형 인간이 되고 싶은데 일정을 어떻게 바꿔야 해?
```

### ❌ 피해야 할 질문 유형
```
- 날씨 어때? (스케줄과 무관)
- 맛있는 음식 추천해줘 (스케줄과 무관)
- 네가 뭘 할 수 있어? (AI 기능 테스트용, 학습 데이터 가치 낮음)
- 응 / 아니 / 알겠어 (너무 짧음)
```

### 💡 데이터 품질을 높이는 팁
1. **구체적으로 질문**하세요: "일정 있어?" 보다 "이번 주 금요일 오후 2시에 비어있어?" 가 더 좋음
2. **AI 답변이 마음에 들면** 그대로 두고, **부족하면 후속 질문**으로 더 좋은 답변 유도
3. **하루에 10~20개** 정도 꾸준히 질문하면 1주일에 100개 달성 가능
4. **다양한 유형**의 질문을 골고루 섞어주세요

---

## 7. Alpaca JSON 추출 방법

충분히 채팅을 나눴다면 (최소 50개 이상 권장), 데이터를 추출합니다.

### 데이터 현황 확인
```powershell
cd project-files
.\venv\Scripts\Activate.ps1

python data_pipeline.py stats
```

출력 예시:
```
=== 데이터 파이프라인 현황 ===
DB 총 레코드: 87개
  평균 품질 점수: 0.72
  품질 0.5 이상: 61개 (70.1%)
  출처별: chat=78, api=9
```

### Alpaca JSON 추출
```powershell
python data_pipeline.py export
```

출력 예시:
```
✅ 학습 데이터 추출 완료
   - 원본: 87개
   - 품질 필터 통과: 61개 (최소 품질: 0.5)
   - train: 54개 → lora_data/processed/alpaca_train.json
   - val:    7개 → lora_data/processed/alpaca_val.json
```

생성된 파일:
```
project-files/
└── lora_data/
    └── processed/
        ├── alpaca_train.json   ← 학습용 (공유 대상)
        └── alpaca_val.json     ← 검증용 (공유 대상)
```

### 파일 내용 확인
```powershell
# 첫 번째 샘플 미리보기
python -c "
import json
with open('lora_data/processed/alpaca_train.json', encoding='utf-8') as f:
    data = json.load(f)
print(f'총 {len(data)}개')
print(json.dumps(data[0], ensure_ascii=False, indent=2))
"
```

출력 예시:
```json
{
  "instruction": "오늘 해야 할 일이 뭐야?",
  "input": "",
  "output": "오늘은 월요일이에요. 오전 9시 영어 공부(⏳ 미완료), 오후 2시 운동(✅ 완료), 저녁 8시 독서가 예정되어 있어요. 현재 미완료 항목은 영어 공부와 독서예요!"
}
```

---

## 8. JSON 파일 공유 방법

### 방법 A — Git으로 공유 (권장)

```powershell
# 브랜치 이름: 자기 팀 이름으로 (예: TeamA, TeamB...)
git checkout -b data/[본인이름]

# JSON 파일 추가
git add project-files/lora_data/processed/

git commit -m "데이터 수집: [본인이름] - [개수]개 Alpaca JSON"

git push origin data/[본인이름]
```

그 다음 팀장(Team A)에게 브랜치 이름 알려주면 팀장이 merge 진행.

### 방법 B — 파일 직접 공유 (카카오톡/Slack)

`project-files/lora_data/processed/` 폴더 안의 파일들을 직접 공유.

파일명은 겹치지 않게 이름 포함:
- `alpaca_train_[본인이름].json`
- `alpaca_val_[본인이름].json`

### 팀장(Team A)이 병합하는 방법
```powershell
cd project-files
.\venv\Scripts\Activate.ps1

# 여러 JSON 파일 병합 (중복 자동 제거)
python data_pipeline.py merge \
  --files lora_data/processed/alpaca_train_A.json \
          lora_data/processed/alpaca_train_B.json \
          lora_data/processed/alpaca_train_C.json \
  --output lora_data/merged/alpaca_train_merged.json
```

---

## 9. 자주 묻는 질문 (FAQ)

### Q: `.\venv\Scripts\Activate.ps1` 실행이 안 돼요
PowerShell 실행 정책 문제입니다:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```
이후 다시 시도하세요.

### Q: `ollama: command not found` 오류가 나요
Ollama가 설치되지 않았거나 PATH 설정이 안 된 것입니다.
1. https://ollama.ai 에서 재설치
2. 터미널 재시작
3. `ollama list` 로 확인

### Q: 채팅 창에서 "AI 백엔드 연결 안됨" 이 뜨는데요
터미널 1 (AI 백엔드, 포트 8001)이 실행 중인지 확인하세요:
```powershell
curl http://localhost:8001/health
```
AI 서버가 꺼져있으면 터미널 1에서 `python ai_backend.py` 다시 실행.

### Q: `python data_pipeline.py stats` 에서 "0개" 가 뜨는데요
채팅이 아직 DB에 기록되지 않은 것입니다:
- 서버가 제대로 실행 중인지 확인
- 브라우저에서 채팅을 몇 번 해보고 다시 시도
- `project-files/data/planquest.db` 파일이 생성되었는지 확인

### Q: 품질 점수가 너무 낮게 나와요 (0.5 미만이 많아요)
품질 점수는 다음 기준으로 책정됩니다:
- 답변 길이 (너무 짧으면 감점)
- 질문과 답변의 연관성
- 스케줄 관련 내용 포함 여부

→ **6. 좋은 학습 데이터를 위한 채팅 방법** 섹션의 예시처럼 더 구체적인 질문을 해보세요.

### Q: index.lock 오류가 계속 나요
```powershell
Remove-Item ".git\index.lock" -Force
Remove-Item ".git\HEAD.lock" -Force
```
그 다음 git 명령어 다시 실행.

### Q: `sqlcipher3` 설치 오류가 나요
```powershell
pip uninstall sqlcipher3
pip install sqlcipher3-binary
```

---

## 📌 데이터 수집 목표 및 일정

| 주차 | 목표 | 내용 |
|------|------|------|
| 5주차 | 각자 100개+ 수집 | 서버 실행 후 활발히 채팅 |
| 6주차 초 | JSON 제출 | 팀장에게 alpaca_train.json 공유 |
| 6주차 중 | 팀장 병합 | 전체 500개+ 데이터셋 완성 |
| 6주차 말 | LoRA 학습 시작 | `python lora_trainer.py` 실행 |

---

## 💬 문의

데이터 수집이나 설치 관련 문의는 팀 단톡방에 남겨주세요!  
Team A (AI 엔진 담당)가 도와드릴게요.

---
*마지막 업데이트: 2026-05-18*
