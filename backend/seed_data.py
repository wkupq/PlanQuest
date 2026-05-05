"""상점 초기 데이터 시드 - 이미지 기반 캐릭터 시스템"""
from database import engine, SessionLocal, Base
from models import ShopItem, UserProfile

# === 캐릭터 이미지 기반 상점 아이템 ===
# image_url: frontend/public/images/characters/ 폴더 안의 PNG 파일명
# 이미지를 추가하면 자동으로 상점에 표시됩니다
SHOP_ITEMS = [
    # === 캐릭터 (Character) ===
    # image_url에 실제 이미지 파일명을 넣으세요 (예: "blue_dragon.png")
    # 이미지가 없으면 emoji가 대체로 표시됩니다

    # --- Common (Lv.1) ---
    {"name": "불꽃공룡", "category": "character", "price": 3, "emoji": "🦖",
     "image_url": "flame_dino.png",
     "description": "머리에 불꽃 왕관을 쓴 아기 공룡", "rarity": "common", "unlock_level": 1},

    {"name": "물방울룡", "category": "character", "price": 3, "emoji": "🐉",
     "image_url": "water_dragon.png",
     "description": "물속성 아기 드래곤", "rarity": "common", "unlock_level": 1},

    {"name": "숲토끼", "category": "character", "price": 3, "emoji": "🐰",
     "image_url": "forest_rabbit.png",
     "description": "숲에서 온 귀여운 토끼", "rarity": "common", "unlock_level": 1},

    {"name": "불꽃여우", "category": "character", "price": 4, "emoji": "🦊",
     "image_url": "fire_fox.png",
     "description": "꼬리에 불꽃이 타오르는 여우", "rarity": "common", "unlock_level": 1},

    {"name": "구름양", "category": "character", "price": 3, "emoji": "🐑",
     "image_url": "cloud_sheep.png",
     "description": "구름처럼 폭신한 양", "rarity": "common", "unlock_level": 1},

    # --- Rare (Lv.3) ---
    {"name": "번개호랑이", "category": "character", "price": 8, "emoji": "🐯",
     "image_url": "thunder_tiger.png",
     "description": "번개를 두른 호랑이", "rarity": "rare", "unlock_level": 3},

    {"name": "달빛사슴", "category": "character", "price": 8, "emoji": "🦌",
     "image_url": "moon_deer.png",
     "description": "뿔에서 달빛이 나는 사슴", "rarity": "rare", "unlock_level": 3},

    {"name": "바람매", "category": "character", "price": 10, "emoji": "🦅",
     "image_url": "wind_hawk.png",
     "description": "바람을 가르는 매", "rarity": "rare", "unlock_level": 3},

    # --- Epic (Lv.5) ---
    {"name": "얼음늑대", "category": "character", "price": 15, "emoji": "🐺",
     "image_url": "ice_wolf.png",
     "description": "얼음 갑옷을 입은 늑대", "rarity": "epic", "unlock_level": 5},

    {"name": "크리스탈곰", "category": "character", "price": 18, "emoji": "🐻",
     "image_url": "crystal_bear.png",
     "description": "수정으로 빛나는 곰", "rarity": "epic", "unlock_level": 5},

    # --- Legendary (Lv.8) ---
    {"name": "천상의유니콘", "category": "character", "price": 30, "emoji": "🦄",
     "image_url": "celestial_unicorn.png",
     "description": "하늘에서 내려온 유니콘", "rarity": "legendary", "unlock_level": 8},

    {"name": "고대용", "category": "character", "price": 50, "emoji": "🐲",
     "image_url": "ancient_dragon.png",
     "description": "전설 속 고대 드래곤", "rarity": "legendary", "unlock_level": 10},
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
        print(f"[SEED] {len(SHOP_ITEMS)}개 캐릭터 아이템 생성 완료")

    db.close()


if __name__ == "__main__":
    seed_database()
    print("데이터베이스 시드 완료!")
