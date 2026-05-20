from auth_manager import get_credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import datetime

SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_calendar_service():
    creds = get_credentials(SCOPES)
    return build('calendar', 'v3', credentials=creds)

# Rate Limit 대응 데코레이터
retry_on_rate_limit = retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=16),
    retry=retry_if_exception_type(HttpError)
)

# 1. Create (생성)
@retry_on_rate_limit
def create_event(service, summary, start_time, end_time):
    event = {
        'summary': summary,
        'start': {'dateTime': start_time, 'timeZone': 'Asia/Seoul'},
        'end': {'dateTime': end_time, 'timeZone': 'Asia/Seoul'},
    }
    created_event = service.events().insert(calendarId='primary', body=event).execute()
    return created_event['id']

# 2. Read (조회)
@retry_on_rate_limit
def read_events(service, time_min, time_max=None):
    events_result = service.events().list(
        calendarId='primary', 
        timeMin=time_min, 
        timeMax=time_max, 
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    return events_result.get('items', [])

# 3. Update (수정)
@retry_on_rate_limit
def update_event(service, event_id, new_summary=None, new_start=None, new_end=None):
    event = service.events().get(calendarId='primary', eventId=event_id).execute()
    
    if new_summary:
        event['summary'] = new_summary
    if new_start:
        event['start']['dateTime'] = new_start
    if new_end:
        event['end']['dateTime'] = new_end
        
    updated_event = service.events().update(calendarId='primary', eventId=event_id, body=event).execute()
    return updated_event['id']

# 4. Delete (삭제)
@retry_on_rate_limit
def delete_event(service, event_id):
    service.events().delete(calendarId='primary', eventId=event_id).execute()
    return True

# 5. Raw Data Fetch (캐시용 최신 데이터 추출)
@retry_on_rate_limit
def get_recent_5_events_raw():
    service = get_calendar_service()
    
    # 현재 시간 기준 설정
    now = datetime.datetime.utcnow().isoformat() + 'Z'
    
    # API를 직접 호출하여 순수 리스트 데이터만 반환
    events_result = service.events().list(
        calendarId='primary', 
        timeMin=now,
        maxResults=5, 
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    
    return events_result.get('items', [])