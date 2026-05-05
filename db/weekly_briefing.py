import sqlite3
from datetime import datetime, timedelta

DB_PATH = "assistant.db"

def get_weekly_calendars():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT content, created_at FROM memories
        WHERE memory_type = 'calendar'
        AND date(created_at) >= date('now', '-7 days')
        ORDER BY created_at DESC
    """)
    results = cursor.fetchall()
    conn.close()
    return results

def get_weekly_emails():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT content, created_at FROM memories
        WHERE memory_type = 'email'
        AND date(created_at) >= date('now', '-7 days')
        ORDER BY created_at DESC
    """)
    results = cursor.fetchall()
    conn.close()
    return results

def get_routines():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT content, COUNT(*) as count FROM memories
        WHERE memory_type = 'routine'
        GROUP BY content
        ORDER BY count DESC
    """)
    results = cursor.fetchall()
    conn.close()
    return results

def generate_weekly_briefing():
    print("=== 주간 브리핑 ===")
    print(f"기준일: {datetime.now().strftime('%Y-%m-%d')}\n")

    calendars = get_weekly_calendars()
    print("[ 이번 주 일정 ]")
    if calendars:
        for content, created_at in calendars:
            print(f"  - {content}")
    else:
        print("  등록된 일정 없음")

    emails = get_weekly_emails()
    print(f"\n[ 이번 주 이메일 ({len(emails)}개) ]")
    if emails:
        for content, created_at in emails:
            print(f"  - {content}")
    else:
        print("  수신된 이메일 없음")

    routines = get_routines()
    print("\n[ 루틴 패턴 ]")
    if routines:
        for content, count in routines:
            confidence = (count / sum(c for _, c in routines)) * 100
            print(f"  - {content} ({count}번 반복, 신뢰도: {confidence:.1f}%)")
    else:
        print("  확인된 루틴 없음")

    print("\n=== 브리핑 완료 ===")

if __name__ == "__main__":
    generate_weekly_briefing()