from datetime import datetime
from googleapiclient.discovery import build
from auth_manager import get_credentials

# 읽기 권한 설정
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

def search_upcoming_events():
    # 1. 보안 저장소(keyring)를 통해 인증 정보 가져오기
    creds = get_credentials(SCOPES)
    service = build('calendar', 'v3', credentials=creds)

    # 2. 현재 시간 설정 (ISO 8601 포맷)
    now = datetime.utcnow().isoformat() + 'Z' 

    print('최근 5개의 일정을 조회합니다...')

    # 3. 일정 리스트 호출
    events_result = service.events().list(
        calendarId='primary', 
        timeMin=now,           # 현재 시간 이후부터
        maxResults=5,          # 최대 5개만
        singleEvents=True,
        orderBy='startTime'    # 시작 시간 순으로 정렬
    ).execute()
    
    events = events_result.get('items', [])

    # 4. 결과 출력
    if not events:
        print('예정된 일정이 없습니다.')
        return

    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        # 시간 형식 가독성 있게 조정 (선택 사항)
        display_time = start.replace('T', ' ').split('+')[0]
        print(f"일시: {display_time} | 제목: {event.get('summary', '제목 없음')}")

if __name__ == '__main__':
    search_upcoming_events()