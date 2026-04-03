# 습관의 숲 (Habit Forest)

AI 비서와 연동되는 습관 관리 + 수집형 게임

## 빠른 시작

### 1. 백엔드 실행
```bash
cd backend
pip install -r requirements.txt
python main.py
```
→ http://127.0.0.1:8000 에서 API 서버 실행
→ http://127.0.0.1:8000/docs 에서 API 문서 확인

### 2. 프론트엔드 실행
```bash
cd frontend
npm install
npm start
```
→ http://localhost:3000 에서 게임 실행

## 주요 기능
- 아이소메트릭 맵 (6x6 그리드)
- 습관 추가 → 씨앗 심기 → 습관 완료 시 나무 성장
- 나무 클릭으로 하트 수확
- 상점에서 동물/나무/건물 구매
- 구매한 아이템 맵에 배치

## 기술 스택
- 백엔드: FastAPI + SQLite + SQLAlchemy
- 프론트엔드: React 18
- API 통신: Axios

## 프로젝트 구조
```
habit-forest/
├── backend/
│   ├── main.py          # FastAPI 앱 + API 엔드포인트
│   ├── models.py        # SQLAlchemy DB 모델
│   ├── database.py      # DB 연결 설정
│   ├── seed_data.py     # 상점 초기 데이터
│   └── requirements.txt
└── frontend/
    ├── public/index.html
    └── src/
        ├── App.js              # 메인 앱
        ├── api.js              # API 호출 함수
        ├── components/
        │   ├── IsometricMap.js  # 아이소메트릭 맵
        │   ├── HabitPanel.js    # 습관 목록
        │   ├── HabitForm.js     # 습관 추가 폼
        │   ├── ShopPanel.js     # 상점
        │   ├── InventoryPanel.js # 인벤토리/배치
        │   └── Toast.js         # 토스트 메시지
        └── styles/global.css
```
