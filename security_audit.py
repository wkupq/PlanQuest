"""
Day 13 — 팀원 B
pip-audit 보안 스캔 + 주 1회 자동 실행 (매주 월요일 오전 9시)
"""

import subprocess
from apscheduler.schedulers.background import BackgroundScheduler
from notifier import notify_routine


# ========================
# 보안 스캔 실행 함수
# ========================

def run_audit():
    """
    pip-audit를 실행하여 설치된 패키지의 보안 취약점을 검사.
    취약점 발견 시 터미널 출력 + 데스크탑 알림 전송.
    """
    print("[보안 스캔] pip-audit 실행 중...")

    result = subprocess.run(
        ['pip-audit'],
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        # 취약점 없음
        print("[보안 스캔] ✅ 취약점이 발견되지 않았습니다.")
    else:
        # 취약점 발견
        print("[보안 스캔] ⚠️ 취약점이 발견되었습니다!")
        print(result.stdout)
        notify_routine(
            routine_name='보안 경고',
            message='pip-audit에서 취약점이 발견되었습니다. 터미널을 확인하세요.'
        )


# ========================
# 스케줄러 등록
# ========================

def start_audit_scheduler():
    """매주 월요일 오전 9시에 자동으로 보안 스캔 실행"""
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_audit,
        trigger='cron',
        day_of_week='mon',
        hour=9,
        minute=0,
        id='pip_audit_scan'
    )
    scheduler.start()
    print("[스케줄러] 보안 스캔 매주 월요일 오전 9시 등록 완료")
    return scheduler


# ========================
# 동작 확인용 테스트
# ========================

if __name__ == '__main__':
    print("=== pip-audit 보안 스캔 테스트 ===\n")
    run_audit()
