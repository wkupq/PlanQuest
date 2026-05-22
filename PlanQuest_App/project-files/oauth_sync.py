"""
oauth_sync.py — Google OAuth 초기 인증 및 연결 테스트
-------------------------------------------------------
이 파일을 직접 실행해서 Google 인증을 완료하세요:
    python oauth_sync.py

인증 완료 후 토큰이 keyring에 저장되며,
백엔드 서버(chat.py, google_sync.py)에서 자동으로 사용됩니다.

스코프:
- gmail.readonly   : Gmail 읽기
- calendar.readonly: Google Calendar 읽기

옵션:
    --reset   기존 토큰 삭제 후 재인증
    --status  저장된 토큰 상태만 확인
"""
import base64
import sys
import os

# project-files 경로 설정 (단독 실행 시)
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)

from auth_manager import get_credentials, check_credentials_status, clear_credentials
from googleapiclient.discovery import build

# Gmail + Calendar 모두 필요 (chat.py / google_sync.py 와 동일한 스코프)
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/calendar.readonly',
]


def get_gmail_service():
    creds = get_credentials(SCOPES)
    return build('gmail', 'v1', credentials=creds)


def get_calendar_service():
    creds = get_credentials(SCOPES)
    return build('calendar', 'v3', credentials=creds)


def test_gmail_connection():
    """Gmail 연결 테스트: 최근 미확인 메일 5건 출력"""
    print("\n--- Gmail 연결 테스트 ---")
    try:
        service = get_gmail_service()
        results = service.users().messages().list(
            userId='me', q='is:unread', maxResults=5
        ).execute()
        messages = results.get('messages', [])

        if not messages:
            print("미확인 이메일이 없습니다.")
        else:
            print(f"미확인 이메일 {len(messages)}건:")
            for m in messages:
                msg = service.users().messages().get(
                    userId='me', id=m['id'],
                    format='metadata',
                    metadataHeaders=['Subject', 'From'],
                ).execute()
                headers = msg['payload']['headers']
                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '(제목 없음)')
                sender  = next((h['value'] for h in headers if h['name'] == 'From'), '(발신자 없음)')
                print(f"  - [{sender[:35]}]")
                print(f"    {subject[:60]}")
        print("✅ Gmail 연결 성공")
    except Exception as e:
        print(f"❌ Gmail 연결 실패: {e}")


def test_calendar_connection():
    """Google Calendar 연결 테스트: 7일 이내 일정 출력"""
    print("\n--- Google Calendar 연결 테스트 ---")
    try:
        from datetime import datetime, timezone, timedelta
        service = get_calendar_service()
        now = datetime.now(timezone.utc)
        week_later = now + timedelta(days=7)

        events_result = service.events().list(
            calendarId='primary',
            timeMin=now.isoformat(),
            timeMax=week_later.isoformat(),
            maxResults=5,
            singleEvents=True,
            orderBy='startTime',
        ).execute()
        events = events_result.get('items', [])

        if not events:
            print("7일 이내 캘린더 일정이 없습니다.")
        else:
            print(f"7일 이내 일정 {len(events)}건:")
            for e in events:
                start = e['start'].get('dateTime', e['start'].get('date', ''))
                print(f"  - {start[:16]} {e.get('summary', '(제목 없음)')}")
        print("✅ Google Calendar 연결 성공")
    except Exception as e:
        print(f"❌ Google Calendar 연결 실패: {e}")


def search_and_analyze_emails(query: str = '예약 OR 일정', max_results: int = 5):
    """Gmail 키워드 검색 (기존 함수 — 하위 호환)"""
    service = get_gmail_service()
    results = service.users().messages().list(
        userId='me', q=query, maxResults=max_results
    ).execute()
    messages = results.get('messages', [])

    if not messages:
        print("분석할 메일이 없습니다.")
        return

    for message in messages:
        msg = service.users().messages().get(userId='me', id=message['id']).execute()
        payload = msg.get('payload', {})
        headers = payload.get('headers', [])

        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '(제목 없음)')
        print(f"제목: {subject}")

        parts = payload.get('parts', [])
        body = ""
        for part in parts:
            if part.get('mimeType') == 'text/plain':
                data = part.get('body', {}).get('data')
                if data:
                    body = base64.urlsafe_b64decode(data).decode('utf-8')
                    break

        if body:
            if "http://" in body or "https://" in body:
                print("- 경고: 본문에 외부 링크가 포함되어 있습니다.")
            else:
                print("- 안전한 메일입니다.")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description="PlanQuest Google OAuth 초기 인증 및 연결 테스트"
    )
    parser.add_argument(
        '--reset', action='store_true',
        help="기존 저장된 토큰을 삭제하고 재인증"
    )
    parser.add_argument(
        '--status', action='store_true',
        help="저장된 토큰 상태만 확인 (인증 플로우 실행 안 함)"
    )
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("  PlanQuest — Google OAuth 설정")
    print("=" * 60)

    # 상태 확인만
    if args.status:
        status = check_credentials_status(SCOPES)
        print(f"\n토큰 존재: {'✅' if status['has_token'] else '❌'}")
        print(f"유효함:   {'✅' if status['is_valid'] else '❌'}")
        print(f"Refresh:  {'✅' if status['has_refresh'] else '❌'}")
        if status.get('scopes'):
            print(f"스코프:   {status['scopes']}")
        if status.get('error'):
            print(f"오류:     {status['error']}")
        sys.exit(0)

    # 토큰 초기화
    if args.reset:
        deleted = clear_credentials()
        if deleted:
            print("\n기존 토큰을 삭제했습니다. 재인증을 시작합니다...")
        else:
            print("\n삭제할 토큰이 없습니다. 신규 인증을 시작합니다...")

    # 인증 실행
    print("\n[1/2] Google 인증 시작...")
    print("브라우저에서 아래 URL이 자동으로 열립니다.")
    print("열리지 않으면 터미널에 출력된 URL을 복사해 브라우저에 붙여넣으세요.\n")
    try:
        creds = get_credentials(SCOPES)
        print("✅ 인증 성공")
    except Exception as e:
        print(f"❌ 인증 실패: {e}")
        sys.exit(1)

    # 연결 테스트
    print("\n[2/2] 연결 테스트...")
    test_gmail_connection()
    test_calendar_connection()

    print("\n" + "=" * 60)
    print("  설정 완료!")
    print("  백엔드 서버를 재시작하면 Gmail/Calendar가")
    print("  AI 채팅에 자동으로 연동됩니다.")
    print("=" * 60 + "\n")
