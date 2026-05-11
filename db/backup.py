import os
import shutil
import keyring
from datetime import datetime
from cryptography.fernet import Fernet
import base64
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

APP_NAME = "ai_assistant"
BACKUP_DIR = "backups"

# 백업할 파일/폴더 목록
BACKUP_TARGETS = [
    "assistant.db",
    "bm25_index.pkl",
    "config.yaml"
]

def get_encryption_key():
    """keyring에서 암호화 키 가져오기"""
    key = keyring.get_password(APP_NAME, "db_key")
    if key is None:
        raise Exception("암호화 키 없음. setup_security.py 먼저 실행하세요.")

    # keyring에서 가져온 키를 Fernet 키로 변환
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"ai_assistant_salt",
        iterations=100000,
    )
    key_bytes = kdf.derive(key.encode())
    return Fernet(base64.urlsafe_b64encode(key_bytes))

def backup():
    """DB 암호화 백업"""
    print("=== 백업 시작 ===\n")

    # 1. 백업 폴더 생성
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"backup_{timestamp}")
    os.makedirs(backup_path)
    print(f"백업 폴더 생성: {backup_path}")

    # 2. 암호화 키 가져오기
    fernet = get_encryption_key()

    # 3. 파일 암호화 후 저장
    for target in BACKUP_TARGETS:
        if not os.path.exists(target):
            print(f"파일 없음 건너뜀: {target}")
            continue

        with open(target, "rb") as f:
            data = f.read()

        # 파일 내용 암호화
        encrypted = fernet.encrypt(data)

        backup_file = os.path.join(backup_path, target + ".enc")
        with open(backup_file, "wb") as f:
            f.write(encrypted)

        print(f"백업 완료: {target} -> {backup_file}")

    print(f"\n=== 백업 완료 ({timestamp}) ===")
    return backup_path

def restore(backup_path: str):
    """백업에서 복구"""
    print(f"=== 복구 시작: {backup_path} ===\n")

    if not os.path.exists(backup_path):
        print("백업 폴더 없음")
        return False

    # 1. 암호화 키 가져오기
    fernet = get_encryption_key()

    # 2. 암호화된 파일 복구
    for target in BACKUP_TARGETS:
        backup_file = os.path.join(backup_path, target + ".enc")

        if not os.path.exists(backup_file):
            print(f"백업 파일 없음 건너뜀: {backup_file}")
            continue

        with open(backup_file, "rb") as f:
            encrypted = f.read()

        # 복호화
        decrypted = fernet.decrypt(encrypted)

        with open(target, "wb") as f:
            f.write(decrypted)

        print(f"복구 완료: {backup_file} -> {target}")

    print("\n=== 복구 완료 ===")
    return True

if __name__ == "__main__":
    # 백업 실행
    backup_path = backup()

    print()

    # 복구 테스트
    print("=== 복구 테스트 ===")
    restore(backup_path)