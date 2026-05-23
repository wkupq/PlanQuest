"""
migrate_db.py — 기존 DB에 신규 컬럼 추가 (안전한 ALTER TABLE)
image_url (shop_items), last_heart_gen (placed_items) 추가
"""
import sqlite3
import os
import logging

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def get_db_path() -> str:
    """database.py와 동일한 경로: 홈 디렉토리의 habit_forest.db"""
    return os.path.join(os.path.expanduser("~"), "habit_forest.db")


def column_exists(cur: sqlite3.Cursor, table: str, column: str) -> bool:
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())


def migrate():
    db_path = get_db_path()
    if not os.path.exists(db_path):
        logger.info("DB 없음 — 마이그레이션 불필요 (앱 시작 시 자동 생성됨)")
        return

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    changed = False

    # 1) shop_items.image_url
    if not column_exists(cur, "shop_items", "image_url"):
        cur.execute("ALTER TABLE shop_items ADD COLUMN image_url TEXT DEFAULT ''")
        logger.info("✅ shop_items.image_url 컬럼 추가")
        changed = True
    else:
        logger.info("⏭ shop_items.image_url 이미 존재")

    # 2) placed_items.last_heart_gen
    if not column_exists(cur, "placed_items", "last_heart_gen"):
        cur.execute("ALTER TABLE placed_items ADD COLUMN last_heart_gen DATETIME")
        # 기존 행의 last_heart_gen = placed_at (없으면 현재 시각)
        cur.execute("""
            UPDATE placed_items
            SET last_heart_gen = COALESCE(placed_at, CURRENT_TIMESTAMP)
            WHERE last_heart_gen IS NULL
        """)
        logger.info("✅ placed_items.last_heart_gen 컬럼 추가 + 기존 행 초기화")
        changed = True
    else:
        logger.info("⏭ placed_items.last_heart_gen 이미 존재")

    if changed:
        conn.commit()
        logger.info("✅ 마이그레이션 완료")
    else:
        logger.info("이미 최신 스키마 — 변경 없음")

    conn.close()


if __name__ == "__main__":
    migrate()
