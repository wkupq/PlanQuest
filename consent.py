import sqlite3
from datetime import datetime

DB_PATH = 'assistant.db'

# DB 테이블 초기화
def init_consent_table():
    """consent 테이블 생성 (없으면)"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS consent (
                id          INTEGER PRIMARY KEY,
                consented   INTEGER NOT NULL,
                consent_at  TEXT NOT NULL
            )
        ''')
        conn.commit()

# 동의 여부 확인
def has_consented() -> bool:
    """이미 동의한 기록이 있는지 확인"""
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            'SELECT consented FROM consent ORDER BY id DESC LIMIT 1'
        ).fetchone()
    return bool(row and row[0] == 1)

# 개인정보 고지 출력
def show_consent():
    """개인정보 처리 방침 출력"""
    print("\n" + "="*60)
    print("       PlanQuest AI Assistant 개인정보 처리 방침")
    print("="*60)
    print("""
본 앱은 아래와 같은 정보를 수집 및 활용합니다:

1. Google 계정 정보
   - Google Calendar 일정 조회/생성/수정/삭제
   - Gmail 이메일 읽기 (읽기 전용)

2. 로컬 저장 데이터
   - 대화 내역, 루틴, 일정 캐시 (기기 내 암호화 저장)
   - Google OAuth 인증 토큰 (OS 보안 저장소에 저장)

3. 수집하지 않는 정보
   - 개인 이메일 내용을 외부 서버로 전송하지 않습니다.
   - 위치 정보, 연락처를 수집하지 않습니다.

수집된 정보는 AI 비서 기능 제공 목적으로만 사용됩니다.
""")
    print("="*60)

# 동의 기록 저장
def record_consent(consented: bool):
    """동의 여부와 시간을 DB에 저장"""
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            'INSERT INTO consent (consented, consent_at) VALUES (?, ?)',
            (1 if consented else 0, now)
        )
        conn.commit()

# 동의 흐름 메인 함수
def run_consent_flow() -> bool:
    """
    최초 실행 시 개인정보 동의 흐름 실행.
    - 이미 동의한 경우: 바로 True 반환
    - 동의 안 한 경우: 고지 출력 후 동의 여부 입력받기
    Returns:
        True  → 동의 완료, 앱 실행 가능
        False → 거부, 앱 종료
    """
    init_consent_table()

    # 이미 동의한 경우
    if has_consented():
        return True

    # 개인정보 고지 출력
    show_consent()

    # 동의 여부 입력
    while True:
        answer = input("위 내용에 동의하십니까? (yes/no): ").strip().lower()
        if answer in ('yes', 'y'):
            record_consent(True)
            print("\n✅ 동의해주셔서 감사합니다. PlanQuest를 시작합니다.\n")
            return True
        elif answer in ('no', 'n'):
            record_consent(False)
            print("\n❌ 동의하지 않으셔서 앱을 종료합니다.\n")
            return False
        else:
            print("yes 또는 no로 입력해주세요.")

# 동작 확인용 테스트
if __name__ == '__main__':
    result = run_consent_flow()
    print(f"동의 결과: {'실행 가능' if result else '앱 종료'}")
