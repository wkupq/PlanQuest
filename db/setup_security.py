import keyring
import yaml
import os
import secrets

APP_NAME = "ai_assistant"
CONFIG_PATH = "config.yaml"

def generate_db_key():
    """DB 암호화 키 생성"""
    # 32바이트 랜덤 키 생성
    key = secrets.token_hex(32)
    return key

def save_key_to_keyring(key: str):
    """생성한 키를 keyring에 안전하게 저장"""
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
            "path": "assistant.db",
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
        }
    }

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)

    # 파일 권한 설정 (읽기/쓰기만 허용)
    os.chmod(CONFIG_PATH, 0o600)
    print("config.yaml 생성 완료")

def setup_security():
    """보안 초기화 전체 실행"""
    print("=== 보안 초기화 시작 ===\n")

    # 1. DB 암호화 키 생성 및 저장
    print("[ 1단계 ] DB 암호화 키 설정")
    key = load_key_from_keyring()
    print(f"키 로드 완료 (길이: {len(key)}자)\n")

    # 2. config.yaml 생성
    print("[ 2단계 ] config.yaml 생성")
    create_config()
    print()

    # 3. 설정 파일 확인
    print("[ 3단계 ] 설정 파일 확인")
    if os.path.exists(CONFIG_PATH):
        print("config.yaml 존재 확인")
    if keyring.get_password(APP_NAME, "db_key"):
        print("keyring 키 존재 확인")

    print("\n=== 보안 초기화 완료 ===")

if __name__ == "__main__":
    setup_security()