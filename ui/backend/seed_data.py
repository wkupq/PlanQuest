"""상점 초기 데이터 시드"""
from database import engine, SessionLocal, Base
from models import ShopItem, UserProfile

SHOP_ITEMS = [
    # === 동물 (Animals) ===
    {"name": "아기 고양이", "category": "animal", "price": 3, "emoji": "🐱", "description": "귀여운 아기 고양이", "rarity": "common", "unlock_level": 1},
    {"name": "강아지", "category": "animal", "price": 5, "emoji": "🐶", "description": "충성스러운 강아지", "rarity": "common", "unlock_level": 1},
    {"name": "토끼", "category": "animal", "price": 4, "emoji": "🐰", "description": "깡충깡충 토끼", "rarity": "common", "unlock_level": 1},
    {"name": "병아리", "category": "animal", "price": 2, "emoji": "🐥", "description": "노란 병아리", "rarity": "common", "unlock_level": 1},
    {"name": "다람쥐", "category": "animal", "price": 6, "emoji": "🐿️", "description": "도토리를 모으는 다람쥐", "rarity": "rare", "unlock_level": 2},
    {"name": "여우", "category": "animal", "price": 8, "emoji": "🦊", "description": "영리한 여우", "rarity": "rare", "unlock_level": 3},
    {"name": "사슴", "category": "animal", "price": 10, "emoji": "🦌", "description": "우아한 사슴", "rarity": "rare", "unlock_level": 3},
    {"name": "부엉이", "category": "animal", "price": 12, "emoji": "🦉", "description": "지혜로운 부엉이", "rarity": "epic", "unlock_level": 5},
    {"name": "유니콘", "category": "animal", "price": 20, "emoji": "🦄", "description": "전설의 유니콘", "rarity": "legendary", "unlock_level": 7},
    {"name": "용", "category": "animal", "price": 30, "emoji": "🐉", "description": "전설의 드래곤", "rarity": "legendary", "unlock_level": 10},

    # === 나무/꽃 (Trees/Flowers) ===
    {"name": "벚꽃나무", "category": "tree", "price": 4, "emoji": "🌸", "description": "분홍빛 벚꽃나무", "rarity": "common", "unlock_level": 1},
    {"name": "소나무", "category": "tree", "price": 3, "emoji": "🌲", "description": "푸른 소나무", "rarity": "common", "unlock_level": 1},
    {"name": "야자수", "category": "tree", "price": 5, "emoji": "🌴", "description": "열대 야자수", "rarity": "common", "unlock_level": 1},
    {"name": "해바라기", "category": "tree", "price": 2, "emoji": "🌻", "description": "밝은 해바라기", "rarity": "common", "unlock_level": 1},
    {"name": "튤립", "category": "tree", "price": 2, "emoji": "🌷", "description": "알록달록 튤립", "rarity": "common", "unlock_level": 1},
    {"name": "장미", "category": "tree", "price": 3, "emoji": "🌹", "description": "빨간 장미", "rarity": "common", "unlock_level": 2},
    {"name": "단풍나무", "category": "tree", "price": 7, "emoji": "🍁", "description": "가을빛 단풍나무", "rarity": "rare", "unlock_level": 3},
    {"name": "대나무", "category": "tree", "price": 6, "emoji": "🎋", "description": "바람에 흔들리는 대나무", "rarity": "rare", "unlock_level": 3},
    {"name": "세계수", "category": "tree", "price": 25, "emoji": "🌳", "description": "거대한 세계수", "rarity": "legendary", "unlock_level": 8},

    # === 건물/가구 (Buildings/Furniture) ===
    {"name": "나무 벤치", "category": "building", "price": 3, "emoji": "🪑", "description": "쉬어갈 수 있는 벤치", "rarity": "common", "unlock_level": 1},
    {"name": "가로등", "category": "building", "price": 4, "emoji": "🏮", "description": "따뜻한 가로등", "rarity": "common", "unlock_level": 1},
    {"name": "우물", "category": "building", "price": 5, "emoji": "⛲", "description": "소원을 비는 우물", "rarity": "common", "unlock_level": 2},
    {"name": "작은 오두막", "category": "building", "price": 8, "emoji": "🏡", "description": "아늑한 오두막", "rarity": "rare", "unlock_level": 3},
    {"name": "풍차", "category": "building", "price": 10, "emoji": "🏗️", "description": "바람개비 풍차", "rarity": "rare", "unlock_level": 4},
    {"name": "다리", "category": "building", "price": 6, "emoji": "🌉", "description": "작은 나무 다리", "rarity": "rare", "unlock_level": 3},
    {"name": "성", "category": "building", "price": 25, "emoji": "🏰", "description": "웅장한 성", "rarity": "legendary", "unlock_level": 9},
    {"name": "등대", "category": "building", "price": 15, "emoji": "🗼", "description": "바다를 비추는 등대", "rarity": "epic", "unlock_level": 6},
]


def seed_database():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # 유저 프로필 생성 (없으면)
    user = db.query(UserProfile).first()
    if not user:
        user = UserProfile(id=1, hearts=5, level=1, total_hearts_earned=0)
        db.add(user)
        db.commit()

    # 상점 아이템 시드 (없으면)
    if db.query(ShopItem).count() == 0:
        for item_data in SHOP_ITEMS:
            item = ShopItem(**item_data)
            db.add(item)
        db.commit()
        print(f"[SEED] {len(SHOP_ITEMS)}개 상점 아이템 생성 완료")

    db.close()


if __name__ == "__main__":
    seed_database()
    print("데이터베이스 시드 완료!")
