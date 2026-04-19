import re

# 민감정보 정규식 패턴
# 신용카드: 4자리-4자리-4자리-4자리 (구분자: 공백 or 하이픈 or 없음)
CREDIT_CARD_PATTERN = re.compile(
    r'\b(\d{4})[\s\-]?(\d{4})[\s\-]?(\d{4})[\s\-]?(\d{4})\b'
)

# 주민등록번호: 6자리-7자리 (뒷자리 첫 번째 숫자는 노출)
RESIDENT_ID_PATTERN = re.compile(
    r'\b(\d{6})[\-](\d{1})(\d{6})\b'
)

# 전화번호: 010/011/016/017/018/019-XXXX-XXXX 또는 지역번호 02/031 등
PHONE_NUMBER_PATTERN = re.compile(
    r'\b(0\d{1,2})[\s\-]?(\d{3,4})[\s\-]?(\d{4})\b'
)


def mask_credit_card(text: str) -> str:
    """신용카드 번호 마스킹: 앞 4자리만 남기고 **** 처리"""
    return CREDIT_CARD_PATTERN.sub(r'\1-****-****-****', text)


def mask_resident_id(text: str) -> str:
    """주민등록번호 마스킹: 뒷자리 첫 번째 숫자만 노출, 나머지 6자리 마스킹"""
    return RESIDENT_ID_PATTERN.sub(r'\1-\2******', text)


def mask_phone_number(text: str) -> str:
    """전화번호 마스킹: 중간 자리를 ****로 처리"""
    return PHONE_NUMBER_PATTERN.sub(r'\1-****-\3', text)


def mask_all(text: str) -> str:
    """텍스트에서 모든 민감정보를 한 번에 마스킹"""
    text = mask_credit_card(text)
    text = mask_resident_id(text)
    text = mask_phone_number(text)
    return text

# 동작 확인용 테스트
if __name__ == '__main__':
    samples = [
        "고객 신용카드 번호는 1234-5678-9012-3456 입니다.",
        "주민등록번호: 901231-1234567 으로 확인됩니다.",
        "연락처는 010-1234-5678 입니다.",
        "카드: 1234 5678 9012 3456, 주민: 850512-2345678, 전화: 010 9876 5432",
    ]

    print("=== 민감정보 마스킹 테스트 ===\n")
    for sample in samples:
        masked = mask_all(sample)
        print(f"원본  : {sample}")
        print(f"마스킹: {masked}")
        print()
