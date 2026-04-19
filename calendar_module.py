from auth_manager import get_credentials
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_calendar_service():
    creds = get_credentials(SCOPES)
    return build('calendar', 'v3', credentials=creds)

# 1. Create (생성)
def create_event(service, summary, start_time, end_time):
    event = {
        'summary': summary,
        'start': {'dateTime': start_time, 'timeZone': 'Asia/Seoul'},
        'end': {'dateTime': end_time, 'timeZone': 'Asia/Seoul'},
    }
    created_event = service.events().insert(calendarId='primary', body=event).execute()
    return created_event['id']

# 2. Read (조회)
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
def delete_event(service, event_id):
    service.events().delete(calendarId='primary', eventId=event_id).execute()
    return True