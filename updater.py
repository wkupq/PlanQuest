import requests
from notifier import notify_routine

# 현재 앱 버전
CURRENT_VERSION = "v0.1.0"

# GitHub 레포 정보
GITHUB_REPO = "wkupq/PlanQuest"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

# 버전 조회 함수
def get_current_version() -> str:
    """현재 앱 버전 반환"""
    return CURRENT_VERSION


def get_latest_version() -> str | None:
    """
    GitHub Releases API로 최신 버전 태그 조회.
    실패 시 None 반환.
    """
    try:
        response = requests.get(GITHUB_API_URL, timeout=5)
        response.raise_for_status()
        return response.json().get('tag_name')
    except Exception as e:
        print(f"[업데이트 확인 실패] {e}")
        return None

# 버전 비교 및 알림
def check_for_update():
    """
    현재 버전과 최신 버전을 비교하여
    새 버전이 있으면 터미널 출력 + 데스크탑 알림 전송.
    """
    print(f"[업데이트 확인] 현재 버전: {CURRENT_VERSION}")

    latest = get_latest_version()

    if latest is None:
        print("[업데이트 확인] 버전 정보를 가져올 수 없습니다.")
        return

    print(f"[업데이트 확인] 최신 버전: {latest}")

    if latest == CURRENT_VERSION:
        print("[업데이트 확인] ✅ 최신 버전을 사용 중입니다.")
    else:
        print(f"[업데이트 확인] 🆕 새 버전이 있습니다! {CURRENT_VERSION} → {latest}")
        notify_routine(
            routine_name='업데이트 알림',
            message=f'새 버전 {latest}이 출시되었습니다!'
        )

# 동작 확인용 테스트
if __name__ == '__main__':
    print("=== 업데이트 확인 테스트 ===\n")
    check_for_update()
