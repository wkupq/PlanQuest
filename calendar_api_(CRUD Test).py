import os.path
import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# 쓰기 권한이 포함된 새로운 범위
SCOPES = ['https://www.googleapis.com/auth/calendar']

def main():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    try:
        service = build('calendar', 'v3', credentials=creds)
        
        # 1. Insert (생성)
        event = {
            'summary': 'PlanQuest 테스트 일정',
            'start': {'dateTime': '2026-03-30T10:00:00+09:00', 'timeZone': 'Asia/Seoul'},
            'end': {'dateTime': '2026-03-30T11:00:00+09:00', 'timeZone': 'Asia/Seoul'},
        }
        created_event = service.events().insert(calendarId='primary', body=event).execute()
        event_id = created_event.get('id')
        print("1. 일정 생성 완료:", created_event.get('summary'))

        # 2. Update (수정)
        created_event['summary'] = 'PlanQuest 수정된 일정'
        updated_event = service.events().update(calendarId='primary', eventId=event_id, body=created_event).execute()
        print("2. 일정 수정 완료:", updated_event.get('summary'))

        # 3. Freebusy (빈 시간 조회)
        now = datetime.datetime.utcnow().isoformat() + 'Z'
        end = (datetime.datetime.utcnow() + datetime.timedelta(days=1)).isoformat() + 'Z'
        freebusy_req = {
            "timeMin": now,
            "timeMax": end,
            "items": [{"id": 'primary'}]
        }
        freebusy_res = service.freebusy().query(body=freebusy_req).execute()
        print("3. 빈 시간 조회 완료:", freebusy_res['calendars']['primary'])

        # 4. Delete (삭제)
        service.events().delete(calendarId='primary', eventId=event_id).execute()
        print("4. 일정 삭제 완료")

    except Exception as error:
        print(f"에러가 발생했습니다: {error}")

if __name__ == '__main__':
    main()