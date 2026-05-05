"""
DB 스키마 마이그레이션 — 누락된 컬럼 자동 추가.

언제 쓰는지:
  models.py 에 새 컬럼이 추가됐는데 SQLite DB 파일이 옛날 스키마라서
  "no such column: ..." 에러가 날 때.

사용법:
  cd backend
  python migrate_db.py

실행 결과:
  ~/habit_forest.db 에서 누락된 컬럼들을 ALTER TABLE 로 추가.
  데이터는 보존됨.
"""
import os
import sqlite3
import sys

# database.py 와 동일한 경로
DB_PATH = os.path.join(os.path.expanduser("~"), "habit_forest.db")

# 각 테이블별로 "있어야 하는 컬럼: SQL 정의" 매핑.
# 나중에 모델에 새 컬럼 추가되면 여기에도 추가하면 됨.
REQUIRED_COLUMNS = {
    "shop_items": {
        "image_url":    "TEXT DEFAULT ''",
        "description":  "TEXT DEFAULT ''",
        "rarity":       "TEXT DEFAULT 'common'",
        "unlock_level": "INTEGER DEFAULT 1",
    },
    "habits": {
        "alarm_enabled":  "BOOLEAN DEFAULT 1",
        "hearts_reward":  "INTEGER DEFAULT 1",
        "streak":         "INTEGER DEFAULT 0",
        "completed_today": "BOOLEAN DEFAULT 0",
        "last_completed":  "DATETIME",
    },
    "trees_on_map": {
        "growth_stage":     "INTEGER DEFAULT 0",
        "hearts_available": "INTEGER DEFAULT 0",
        "last_harvest":     "DATETIME",
    },
    "user_profile": {
        "level":               "INTEGER DEFAULT 1",
        "total_hearts_earned": "INTEGER DEFAULT 0",
    },
    # W3 D4-6: RAG 메모리
    "user_memory": {
        "memory_type":      "TEXT DEFAULT 'conversation'",
        "content":          "TEXT",
        "chroma_id":        "TEXT DEFAULT ''",
        "importance_score": "REAL DEFAULT 0.5",
        "access_count":     "INTEGER DEFAULT 0",
        "last_accessed":    "DATETIME",
        "created_at":       "DATETIME",
    },
}


def migrate():
    if not os.path.exists(DB_PATH):
        print(f"[INFO] DB 파일이 아직 없습니다: {DB_PATH}")
        print("       백엔드를 한 번 실행하면 자동 생성됩니다.")
        return

    print(f"[OK] DB 파일 발견: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    total_added = 0
    for table, cols in REQUIRED_COLUMNS.items():
        # 테이블 존재 확인
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
        if not cur.fetchone():
            print(f"[SKIP] {table} 테이블 없음 (백엔드 실행 시 자동 생성됨)")
            continue

        # 현재 컬럼 목록
        cur.execute(f"PRAGMA table_info({table})")
        existing = {row[1] for row in cur.fetchall()}

        # 누락된 것만 추가
        added_here = []
        for col, type_def in cols.items():
            if col not in existing:
                try:
                    cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {type_def}")
                    added_here.append(col)
                    total_added += 1
                except sqlite3.OperationalError as e:
                    print(f"[FAIL] {table}.{col} 추가 실패: {e}")

        if added_here:
            print(f"[ADD] {table}: {', '.join(added_here)}")
        else:
            print(f"[OK]  {table}: 이상 없음")

    conn.commit()
    conn.close()

    if total_added:
        print(f"\n총 {total_added}개 컬럼 추가됨. 이제 백엔드를 다시 실행하세요:")
    else:
        print(f"\n변경사항 없음. 백엔드 그대로 실행하세요:")
    print("  python main.py")


if __name__ == "__main__":
    try:
        migrate()
    except Exception as e:
        print(f"\n[ERROR] {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
