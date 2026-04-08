import sqlite3
import os

DB_PATH = "assistant.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # WAL 모드 활성화
    cursor.execute("PRAGMA journal_mode=WAL")
    result = cursor.fetchone()
    print(f"Journal mode: {result[0]}")

    # 기본 테이블 생성
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    print("assistant.db 초기화 완료")

if __name__ == "__main__":
    init_db()