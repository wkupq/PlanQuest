import re
from loguru import logger

# 로그 파일 설정
logger.add(
    "logs/app.log",
    rotation="1 day",    # 하루마다 새 파일
    retention="7 days",  # 7일치만 보관
    encoding="utf-8"
)

# 마스킹할 패턴 목록
MASKING_PATTERNS = [
    # 이메일 주소
    (r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "***@***.***"),
    # 전화번호
    (r"01[0-9]-\d{4}-\d{4}", "***-****-****"),
    # 신용카드 번호
    (r"\d{4}-\d{4}-\d{4}-\d{4}", "****-****-****-****"),
    # 주민번호
    (r"\d{6}-[1-4]\d{6}", "******-*******"),
]

def mask_sensitive_data(text: str) -> str:
    """민감정보 마스킹 처리"""
    masked = text
    for pattern, replacement in MASKING_PATTERNS:
        masked = re.sub(pattern, replacement, masked)
    return masked

class MaskingFilter:
    """loguru 로그 마스킹 필터"""
    def __call__(self, record):
        record["message"] = mask_sensitive_data(record["message"])
        return True

def get_logger():
    """마스킹 필터 적용된 로거 반환"""
    logger.remove()  # 기본 로거 제거

    # 마스킹 필터 추가
    masking_filter = MaskingFilter()

    # 터미널 출력
    logger.add(
        sink=lambda msg: print(msg, end=""),
        filter=masking_filter,
        format="{time:HH:mm:ss} | {level} | {message}"
    )

    # 파일 저장
    logger.add(
        "logs/app.log",
        filter=masking_filter,
        rotation="1 day",
        retention="7 days",
        encoding="utf-8"
    )

    return logger

if __name__ == "__main__":
    import os
    os.makedirs("logs", exist_ok=True)

    log = get_logger()

    print("=== 로그 마스킹 테스트 ===\n")

    # 1. 일반 로그
    log.info("AI 비서 시작")

    # 2. 이메일 마스킹
    log.info("사용자 이메일: test@example.com 에서 메일 도착")

    # 3. 전화번호 마스킹
    log.info("연락처: 010-1234-5678 저장됨")

    # 4. 신용카드 마스킹
    log.info("결제 정보: 1234-5678-9012-3456")

    # 5. 주민번호 마스킹
    log.info("사용자 정보: 900101-1234567")