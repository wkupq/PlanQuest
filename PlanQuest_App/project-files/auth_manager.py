"""
auth_manager.py — Google OAuth 자격증명 관리
---------------------------------------------
- keyring에 토큰을 암호화 저장 (client_secret.json / token.json은 미저장)
- 서버 컨텍스트에서 호출 시: open_browser=False로 URL만 출력
  → 사용자가 브라우저에서 URL 열고 인증 완료
- 초기 인증은 oauth_sync.py를 단독 실행하는 것을 권장

보안:
- client_secret.json은 절대 keyring/DB에 저장하지 않음
- token.json 파일로 저장하지 않음 (keyring만 사용)
- 로그에 토큰 값 출력 금지
"""
import logging
import os
import json
import keyring
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

logger = logging.getLogger(__name__)

# client_secret.json 절대경로 (project-files 폴더 기준)
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CLIENT_SECRET_PATH = os.path.join(_BASE_DIR, "client_secret.json")

SERVICE_NAME = "PlanQuest_AI_Assistant"
ACCOUNT_NAME = "google_token"

# OAuth 로컬 콜백 서버 포트 (고정 포트 사용 — redirect_uri 등록 필요)
_OAUTH_PORT = 8085


def _run_oauth_flow(scopes: list) -> Credentials:
    """
    OAuth 플로우 실행.
    1) 브라우저가 열리면 자동 완료
    2) 브라우저가 열리지 않으면 URL을 터미널에 출력하고 대기
    → 사용자가 URL을 복사해 브라우저에서 직접 열면 콜백 수신 완료
    """
    if not os.path.exists(CLIENT_SECRET_PATH):
        raise FileNotFoundError(
            f"client_secret.json 파일이 없습니다: {CLIENT_SECRET_PATH}\n"
            "Google Cloud Console에서 OAuth 2.0 클라이언트를 생성 후 다운로드하세요."
        )

    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_PATH, scopes)

    print("\n" + "=" * 60)
    print("  Google 인증이 필요합니다")
    print("=" * 60)
    print(f"  로컬 콜백 서버를 포트 {_OAUTH_PORT}에서 시작합니다.")
    print("  브라우저가 자동으로 열리지 않으면 아래 URL을 복사해")
    print("  브라우저에서 직접 여세요.")
    print("=" * 60 + "\n")

    try:
        # open_browser=False: 브라우저 강제 오픈 없이 URL 출력
        creds = flow.run_local_server(
            port=_OAUTH_PORT,
            open_browser=False,
            success_message=(
                "✅ Google 인증이 완료되었습니다! "
                "이 브라우저 탭을 닫으셔도 됩니다."
            ),
        )
    except OSError as e:
        # 포트 충돌 시 임의 포트로 재시도
        logger.warning("포트 %d 사용 중 — 임의 포트로 재시도: %s", _OAUTH_PORT, e)
        creds = flow.run_local_server(
            port=0,
            open_browser=False,
            success_message="✅ Google 인증이 완료되었습니다!",
        )

    print("\n✅ 인증 완료 — 토큰을 안전하게 저장합니다.\n")
    return creds


def get_credentials(scopes: list) -> Credentials:
    """
    Google OAuth 자격증명 반환.

    흐름:
    1. keyring에서 저장된 토큰 로드
    2. 유효하면 그대로 반환
    3. 만료됐고 refresh_token이 있으면 자동 갱신
    4. 없거나 갱신 불가 → OAuth 플로우 실행 후 저장

    Raises:
        FileNotFoundError: client_secret.json 없음
        RuntimeError: OAuth 플로우 실패
    """
    creds: Credentials | None = None

    # ── 1. keyring에서 토큰 로드 ──────────────────────────────
    try:
        saved_token = keyring.get_password(SERVICE_NAME, ACCOUNT_NAME)
    except Exception as e:
        logger.warning("keyring 접근 실패 (백엔드 없음?): %s", e)
        saved_token = None

    if saved_token:
        try:
            token_data = json.loads(saved_token)
            creds = Credentials.from_authorized_user_info(token_data, scopes)
        except Exception as e:
            logger.warning("저장된 토큰 파싱 실패 — 재인증 필요: %s", e)
            creds = None

    # ── 2. 유효성 검사 및 갱신 ────────────────────────────────
    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            logger.info("액세스 토큰 만료 — refresh_token으로 갱신 중...")
            creds.refresh(Request())
            logger.info("토큰 갱신 완료")
        except Exception as e:
            logger.warning("토큰 갱신 실패 — 재인증 필요: %s", e)
            creds = None

    # ── 3. OAuth 플로우 실행 ──────────────────────────────────
    if not creds or not creds.valid:
        creds = _run_oauth_flow(scopes)

    # ── 4. 갱신/신규 토큰 keyring에 저장 ─────────────────────
    if creds and creds.valid:
        try:
            keyring.set_password(SERVICE_NAME, ACCOUNT_NAME, creds.to_json())
            logger.info("토큰을 keyring에 안전하게 저장했습니다.")
        except Exception as e:
            logger.error("keyring 저장 실패 (토큰 유실 위험): %s", e)

    return creds


def clear_credentials() -> bool:
    """
    저장된 OAuth 토큰 삭제 (재인증 시 사용).
    Returns: True면 삭제 성공, False면 토큰 없었음
    """
    try:
        existing = keyring.get_password(SERVICE_NAME, ACCOUNT_NAME)
        if existing:
            keyring.delete_password(SERVICE_NAME, ACCOUNT_NAME)
            logger.info("저장된 Google 토큰을 삭제했습니다.")
            return True
        return False
    except Exception as e:
        logger.error("토큰 삭제 실패: %s", e)
        return False


def check_credentials_status(scopes: list) -> dict:
    """
    현재 저장된 토큰 상태 확인 (인증 플로우 실행 없이).
    Returns: {"has_token": bool, "is_valid": bool, "has_refresh": bool, "scopes": list}
    """
    try:
        saved_token = keyring.get_password(SERVICE_NAME, ACCOUNT_NAME)
    except Exception:
        return {"has_token": False, "is_valid": False, "has_refresh": False, "scopes": []}

    if not saved_token:
        return {"has_token": False, "is_valid": False, "has_refresh": False, "scopes": []}

    try:
        token_data = json.loads(saved_token)
        creds = Credentials.from_authorized_user_info(token_data, scopes)
        return {
            "has_token": True,
            "is_valid": creds.valid,
            "has_refresh": bool(creds.refresh_token),
            "scopes": list(token_data.get("scopes", [])),
        }
    except Exception as e:
        return {"has_token": True, "is_valid": False, "has_refresh": False, "scopes": [], "error": str(e)}
