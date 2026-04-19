import base64
from auth_manager import get_credentials
from googleapiclient.discovery import build

# Gmail 읽기 권한 설정
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def get_gmail_service():
    creds = get_credentials(SCOPES)
    return build('gmail', 'v1', credentials=creds)

def search_and_analyze_emails():
    service = get_gmail_service()
    
    # '예약' 또는 '일정'이 포함된 메일 검색
    query = '예약 OR 일정'
    results = service.users().messages().list(userId='me', q=query, maxResults=5).execute()
    messages = results.get('messages', [])

    if not messages:
        print("분석할 메일이 없습니다.")
        return

    for message in messages:
        msg = service.users().messages().get(userId='me', id=message['id']).execute()
        payload = msg.get('payload')
        headers = payload.get('headers')
        
        subject = next(h['value'] for h in headers if h['name'] == 'Subject')
        print(f"제목: {subject}")

        # 본문 데이터 추출 (AI 모델에 전달할 텍스트)
        parts = payload.get('parts')
        body = ""
        if parts:
            for part in parts:
                if part['mimeType'] == 'text/plain':
                    data = part['body'].get('data')
                    if data:
                        body = base64.urlsafe_b64decode(data).decode('utf-8')
        
        #'AI 모델 분석' 단계 (가정)
        if body:
            print("- 본문 분석 중...")
            if "http://" in body or "https://" in body:
                print("- 경고: 본문에 외부 링크가 포함되어 있습니다. 사용자의 확인이 필요합니다.")
            else:
                print("- 안전한 메일입니다. 일정을 추출합니다.")

if __name__ == '__main__':
    search_and_analyze_emails()