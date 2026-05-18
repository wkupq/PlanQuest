# AI 비서 시스템 — 팀원 C 모듈

## 개요
AI 비서의 데이터 저장, 검색, 메모리 관리, 보안을 담당했습니다.

---

## 설치 방법

### 1. 레포 클론
git clone https://github.com/wkupq/c.git
cd c

### 2. 패키지 설치
pip install -r requirements.txt

### 3. 보안 초기화 (처음 한 번만 실행)
python db/setup_security.py

---

## 파일 구조

db/
├── init_db.py            DB 초기화
├── indexer.py            BM25 + ChromaDB 저장
├── retriever.py          RRF 검색 합산
├── pipeline.py           RAG 파이프라인
├── memory.py             메모리 시스템
├── scheduler.py          임계값 트리거
├── check_index.py        정합성 검사
├── notifier.py           알림 발송
├── security.py           프롬프트 인젝션 방어
├── setup_security.py     보안 초기화
├── config_loader.py      설정 파일 로더
├── routine_analyzer.py   루틴 패턴 분석
├── log_masking.py        로그 마스킹
├── weekly_briefing.py    주간 브리핑
├── chroma_cleanup.py     ChromaDB 정리 + BM25 동기화
├── backup.py             암호화 백업/복구
├── error_handler.py      에러 핸들링
└── test_unit.py          단위 테스트

---

## 주요 기능

### RAG 파이프라인
ChromaDB(의미 검색)와 BM25(키워드 검색)를 함께 사용해
RRF 알고리즘으로 합산해 검색 정확도를 높였습니다.
유사도 기준값(0.9)으로 관련 없는 결과는 필터링합니다.

### 메모리 시스템
대화, 이메일, 루틴, 일정을 분류해 저장하고
종류별 TTL 유통기한으로 자동 관리합니다.
임계값 도달 시 스케줄러가 자동으로 정리 트리거를 실행합니다.

### 보안
외부 데이터를 태그로 격리해 프롬프트 인젝션을 방어하고
로그에 개인정보가 남지 않도록 마스킹 처리했습니다.
DB와 설정 파일은 AES-256으로 암호화해 백업합니다.

### 설정 관리
모든 경로와 설정값은 config.yaml에서 관리합니다.
코드를 수정하지 않고 config.yaml만 변경해서 설정을 바꿀 수 있습니다.

---

## 테스트

pytest db/test_unit.py -v

57개 테스트 전부 통과, 커버리지 70% 달성했습니다.

---

## 주의사항

합치기 전에 아래 순서로 진행해주세요.

1. python db/setup_security.py 실행
2. pytest db/test_unit.py -v 실행
3. 57개 테스트 전부 통과 확인
4. 테스트 데이터 삭제 후 합치기

테스트 데이터 삭제 대상:
test_hooks.py, memory.py, routine_analyzer.py 의
if __name__ == "__main__": 아래 테스트 코드 제거 후 합칠 것