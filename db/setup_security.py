import keyring
import yaml
import os
import secrets
import sqlite3
from datetime import datetime

APP_NAME = "ai_assistant"
CONFIG_PATH = "config.yaml"
DB_PATH = "assistant.db"
BACKUP_DIR = "backups"

def generate_db_key():
    """DB 암호화 키 생성"""
    key = secrets.token_hex(32)
    return key

def save_key_to_keyring(key: str):
    """생성한 키를 keyring에 저장"""
    keyring.set_password(APP_NAME, "db_key", key)
    print("DB 암호화 키 keyring 저장 완료")

def load_key_from_keyring():
    """keyring에서 키 불러오기"""
    key = keyring.get_password(APP_NAME, "db_key")
    if key is None:
        print("키 없음 -> 새로 생성")
        key = generate_db_key()
        save_key_to_keyring(key)
    return key

def create_config():
    """config.yaml 생성"""
    config = {
        "app": {
            "name": "AI Assistant",
            "version": "1.0.0"
        },
        "db": {
            "path": DB_PATH,
            "wal_mode": True
        },
        "chromadb": {
            "path": "./chroma_db"
        },
        "memory": {
            "ttl": {
                "conversation": 30,
                "email": 7,
                "routine": 90,
                "calendar": 60
            }
        },
        "security": {
            "similarity_threshold": 0.9,
            "max_tokens": 28000
        },
        "backup": {
            "dir": BACKUP_DIR,
            "interval_days": 7
        }
    }

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)

    os.chmod(CONFIG_PATH, 0o600)
    print("config.yaml 생성 완료")

def init_directories():
    """필요한 폴더 자동 생성"""
    dirs = ["backups", "logs", "chroma_db"]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
        print(f"폴더 생성: {d}/")

def init_database():
    """DB 초기화"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("PRAGMA journal_mode=WAL")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            memory_type TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL
        )
    """)

    conn.commit()
    conn.close()
    print("DB 초기화 완료 (WAL 모드 + 테이블 생성)")

def setup_security():
    """보안 초기화 전체 원클릭 실행"""
    print("=== AI 비서 보안 초기화 시작 ===\n")

    print("[ 1단계 ] 폴더 생성")
    init_directories()
    print()

    print("[ 2단계 ] DB 암호화 키 설정")
    key = load_key_from_keyring()
    print(f"키 로드 완료 (길이: {len(key)}자)")
    print()

    print("[ 3단계 ] config.yaml 생성")
    create_config()
    print()

    print("[ 4단계 ] DB 초기화")
    init_database()
    print()

    print("[ 5단계 ] 설정 확인")
    checks = {
        "config.yaml": os.path.exists(CONFIG_PATH),
        "assistant.db": os.path.exists(DB_PATH),
        "backups/": os.path.exists(BACKUP_DIR),
        "keyring 키": keyring.get_password(APP_NAME, "db_key") is not None
    }
    for name, status in checks.items():
        print(f"  {'통과' if status else '실패'}: {name}")

    print("\n=== 보안 초기화 완료 ===")
    print("이제 AI 비서를 사용할 수 있습니다!")

if __name__ == "__main__":
    setup_security()