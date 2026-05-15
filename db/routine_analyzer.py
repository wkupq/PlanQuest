import sqlite3
from datetime import datetime, timedelta
from collections import Counter

DB_PATH = "assistant.db"

def get_routine_memories():
    """저장된 루틴 메모리 전체 가져오기"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT content, created_at FROM memories WHERE memory_type = 'routine'"
    )
    results = cursor.fetchall()
    conn.close()
    return results

def analyze_routine_pattern():
    """루틴 패턴 분석"""
    memories = get_routine_memories()

    if not memories:
        print("저장된 루틴 없음")
        return None

    # 루틴 내용 빈도 분석
    contents = [content for content, _ in memories]
    counter = Counter(contents)

    print("=== 루틴 패턴 분석 ===")
    for content, count in counter.most_common():
        confidence = (count / len(memories)) * 100
        print(f"  '{content}' → {count}번 반복 (신뢰도: {confidence:.1f}%)")

        if confidence >= 85:
            print(f"  -> 확정된 루틴 패턴!")

    return counter

def add_routine_pattern(content: str):
    """루틴 패턴 추가"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO memories (memory_type, content, expires_at) VALUES (?, ?, ?)",
        ("routine", content, datetime.now() + timedelta(days=90))
    )
    conn.commit()
    conn.close()
    print(f"루틴 추가: {content}")

if __name__ == "__main__":
    print("=== 루틴 패턴 테스트 ===\n")

    # 테스트 루틴 추가
    add_routine_pattern("매일 아침 9시 업무 시작")
    add_routine_pattern("매일 아침 9시 업무 시작")
    add_routine_pattern("매일 아침 9시 업무 시작")
    add_routine_pattern("점심 12시 식사")

    # 패턴 분석
    analyze_routine_pattern()