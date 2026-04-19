import os.path
import json
import keyring
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# 가상의 서비스 이름과 사용자 이름 설정
SERVICE_NAME = "PlanQuest_AI_Assistant"
ACCOUNT_NAME = "google_token"

def get_credentials(scopes):
    creds = None

    # 1. keyring에서 기존 토큰 가져오기
    saved_token = keyring.get_password(SERVICE_NAME, ACCOUNT_NAME)

    if saved_token:
        # JSON 문자열을 사전 객체로 변환 후 Credentials 생성
        token_data = json.loads(saved_token)
        creds = Credentials.from_authorized_user_info(token_data, scopes)

    # 2. 토큰이 없거나 만료된 경우 처리
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # 90일 재발급 로직: Refresh Token을 사용하여 자동으로 토큰 갱신
            creds.refresh(Request())
        else:
            # 최초 인증 실행
            flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', scopes)
            creds = flow.run_local_server(port=0)

        # 3. 새로 발급받거나 갱신된 토큰을 keyring에 보안 저장
        keyring.set_password(SERVICE_NAME, ACCOUNT_NAME, creds.to_json())

    return creds
