# AI 비서 시스템 — 팀원 C 모듈

## 담당 모듈
데이터베이스, 메모리 관리, 검색 파이프라인, 보안

---

## 설치 방법

### 1. 레포 클론
git clone https://github.com/wkupq/c.git
cd c

### 2. 패키지 설치
pip install -r requirements.txt

### 3. 보안 초기화 (처음 한 번만)
python db/setup_security.py

---

## 파일 구조
db/
├── init_db.py          DB 초기화
├── chroma_test.py      ChromaDB 테스트
├── indexer.py          BM25 + ChromaDB 저장
├── retriever.py        RRF 검색 합산
├── pipeline.py         RAG 파이프라인
├── memory.py           메모리 시스템
├── scheduler.py        임계값 트리거
├── check_index.py      정합성 검사
├── notifier.py         알림 발송
├── security.py         프롬프트 인젝션 방어
├── setup_security.py   보안 초기화
├── routine_analyzer.py 루틴 패턴 분석
├── log_masking.py      로그 마스킹
├── weekly_briefing.py  주간 브리핑
├── verify_triggers.py  트리거 검증
├── chroma_cleanup.py   ChromaDB 정리
├── backup.py           백업/복구
└── test_unit.py        pytest 단위 테스트

---

## 주요 기능

### RAG 파이프라인
의미 기반 검색(ChromaDB)과 키워드 기반 검색(BM25)을
RRF 알고리즘으로 합산해서 검색 정확도를 높였습니다.

### 메모리 시스템
대화, 이메일, 루틴, 일정 4종류로 메모리를 분류하고
종류별 TTL 유통기한을 설정해서 자동으로 관리합니다.

### 보안
프롬프트 인젝션 방어, 로그 마스킹,
AES-256 암호화 백업을 적용했습니다.

---

## 테스트 실행

pytest db/test_unit.py -v

---

합치기 전에:
1. python db/setup_security.py 실행
2. pytest db/test_unit.py -v 실행
3. 테스트 전부 통과 확인 후 합치기