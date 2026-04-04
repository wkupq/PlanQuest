from auth_manager import get_credentials
from googleapiclient.discovery import build

# Calendar + Gmail 권한을 통합하여 요청 (토큰 하나로 두 API 모두 커버)
SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/gmail.readonly'
]

def main():
    creds = get_credentials(SCOPES)

    try:
        service = build('gmail', 'v1', credentials=creds)
        print('최신 이메일 10건을 가져옵니다.')
        
        results = service.users().messages().list(userId='me', maxResults=10).execute()
        messages = results.get('messages', [])

        if not messages:
            print('메시지가 없습니다.')
            return

        for message in messages:
            msg = service.users().messages().get(
                userId='me', 
                id=message['id'], 
                format='metadata', 
                metadataHeaders=['Subject', 'From']
            ).execute()
            
            headers = msg['payload']['headers']
            subject = next((header['value'] for header in headers if header['name'] == 'Subject'), '제목 없음')
            sender = next((header['value'] for header in headers if header['name'] == 'From'), '발신자 알 수 없음')
            
            print(f"보낸사람: {sender} | 제목: {subject}")

    except Exception as error:
        print(f"에러가 발생했습니다: {error}")

if __name__ == '__main__':
    main()