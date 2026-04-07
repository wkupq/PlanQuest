import sqlite3
from auth_manager import get_credentials
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
DB_PATH = 'assistant.db'

# sync_checkpoint 테이블 초기화
def init_db():
    """sync_checkpoint 테이블 생성 (없으면)"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS sync_checkpoint (
                id      INTEGER PRIMARY KEY,
                service TEXT UNIQUE NOT NULL,
                value   TEXT NOT NULL
            )
        ''')
        conn.commit()

# historyId 저장 / 불러오기
def get_saved_history_id() -> str | None:
    """DB에 저장된 마지막 historyId 반환"""
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            'SELECT value FROM sync_checkpoint WHERE service = ?',
            ('gmail',)
        ).fetchone()
    return row[0] if row else None


def save_history_id(history_id: str):
    """현재 historyId를 DB에 저장 (없으면 insert, 있으면 update)"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            INSERT INTO sync_checkpoint (service, value)
            VALUES ('gmail', ?)
            ON CONFLICT(service) DO UPDATE SET value = excluded.value
        ''', (history_id,))
        conn.commit()

# Gmail 서비스 초기화
def get_gmail_service():
    creds = get_credentials(SCOPES)
    return build('gmail', 'v1', credentials=creds)

# 증분 동기화 메인 함수
def sync_gmail():
    """
    저장된 historyId 이후의 새 메일만 가져오는 증분 동기화.
    - 최초 실행: 현재 historyId를 저장하고 종료 (기준점 설정)
    - 이후 실행: 변경 내역(신규 메일)만 조회
    """
    init_db()
    service = get_gmail_service()

    saved_id = get_saved_history_id()

    if not saved_id:
        # 최초 실행 — 현재 historyId를 기준점으로 저장
        profile = service.users().getProfile(userId='me').execute()
        current_id = str(profile['historyId'])
        save_history_id(current_id)
        print(f"[최초 실행] 기준 historyId 저장 완료: {current_id}")
        print("다음 실행부터 새 메일을 감지합니다.")
        return

    # 증분 동기화 — 저장된 historyId 이후의 변경 내역 조회
    print(f"[증분 동기화] 마지막 historyId: {saved_id} 이후 변경 내역 조회 중...")

    try:
        response = service.users().history().list(
            userId='me',
            startHistoryId=saved_id,
            historyTypes=['messageAdded']
        ).execute()

        new_messages = []
        for record in response.get('history', []):
            for msg in record.get('messagesAdded', []):
                new_messages.append(msg['message']['id'])

        if not new_messages:
            print("새로운 메일이 없습니다.")
        else:
            print(f"새 메일 {len(new_messages)}건 감지:")
            for msg_id in new_messages:
                msg = service.users().messages().get(
                    userId='me',
                    id=msg_id,
                    format='metadata',
                    metadataHeaders=['Subject', 'From']
                ).execute()
                headers = msg['payload']['headers']
                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '제목 없음')
                sender  = next((h['value'] for h in headers if h['name'] == 'From'), '발신자 알 수 없음')
                print(f"  - [{sender}] {subject}")

        # 최신 historyId 갱신
        latest_id = response.get('historyId', saved_id)
        save_history_id(str(latest_id))
        print(f"[체크포인트 갱신] historyId: {latest_id}")

    except Exception as e:
        # historyId 만료 시 (구글은 7일 이상 지나면 만료)
        if 'historyId' in str(e):
            print("[경고] historyId 만료 — 기준점 재설정합니다.")
            profile = service.users().getProfile(userId='me').execute()
            save_history_id(str(profile['historyId']))
        else:
            print(f"[오류] {e}")


if __name__ == '__main__':
    sync_gmail()
