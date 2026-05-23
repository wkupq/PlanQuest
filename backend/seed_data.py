"""상점 초기 데이터 시드 - 이미지 기반 캐릭터 시스템"""
from database import engine, SessionLocal, Base
from models import ShopItem, UserProfile

# === 캐릭터 이미지 기반 상점 아이템 ===
# image_url: frontend/public/images/characters/ 폴더 안의 PNG 파일명
# 추후 캐릭터 추가 시 PNG를 frontend/public/images/characters/에 두고 이 리스트에 추가
SHOP_ITEMS = [
    # === Common (Lv.1) ===
    {"name": "불꽃포메",     "category": "character", "price": 6,  "emoji": "🔥",
     "image_url": "flame_pom.png",
     "description": "머리에 불꽃을 단 통통한 포메라니안",        "rarity": "common",    "unlock_level": 1},

    {"name": "달빛토끼",     "category": "character", "price": 8,  "emoji": "🌙",
     "image_url": "moon_bunny.png",
     "description": "이마에 황금 초승달이 빛나는 토끼",          "rarity": "common",    "unlock_level": 1},

    {"name": "눈구름냥",     "category": "character", "price": 8,  "emoji": "❄️",
     "image_url": "snow_cat.png",
     "description": "구름 같은 꼬리에 솜털 갈기 가진 흰 고양이", "rarity": "common",    "unlock_level": 1},

    {"name": "알파카",       "category": "character", "price": 10, "emoji": "🦙",
     "image_url": "alpaca.png",
     "description": "컬러풀한 술 장식을 한 친근한 알파카",        "rarity": "common",    "unlock_level": 1},

    {"name": "카피바라",     "category": "character", "price": 8,  "emoji": "🦦",
     "image_url": "capybara.png",
     "description": "느긋한 표정의 통통한 카피바라",              "rarity": "common",    "unlock_level": 1},

    {"name": "불꽃펭귄",     "category": "character", "price": 10, "emoji": "🐧",
     "image_url": "flame_penguin.png",
     "description": "머리에 작은 불꽃을 얹은 아기 펭귄",          "rarity": "common",    "unlock_level": 1},

    {"name": "호랑햄스터",   "category": "character", "price": 8,  "emoji": "🐹",
     "image_url": "tiger_hamster.png",
     "description": "호랑이 줄무늬가 매력적인 통통한 햄스터",     "rarity": "common",    "unlock_level": 1},

    # === Rare (Lv.2) ===
    {"name": "라벤더냥",     "category": "character", "price": 12, "emoji": "💜",
     "image_url": "lavender_cat.png",
     "description": "이마에 별이 빛나는 라벤더빛 고양이",         "rarity": "rare",      "unlock_level": 2},

    {"name": "소나무",       "category": "character", "price": 14, "emoji": "🌲",
     "image_url": "mystic_tree.png",
     "description": "푸른 잎이 무성한 신비로운 소나무",           "rarity": "rare",      "unlock_level": 2},

    {"name": "파파야나무",   "category": "character", "price": 12, "emoji": "🌴",
     "image_url": "papaya_tree.png",
     "description": "잘 익은 파파야 열매가 달린 열대 나무",       "rarity": "rare",      "unlock_level": 2},

    {"name": "음악수달",     "category": "character", "price": 14, "emoji": "🎧",
     "image_url": "music_otter.png",
     "description": "헤드폰을 쓰고 조개 가방을 멘 수달",          "rarity": "rare",      "unlock_level": 2},

    # === Unique (Lv.3+) ===
    {"name": "무지개여우",   "category": "character", "price": 20, "emoji": "🌈",
     "image_url": "rainbow_fox.png",
     "description": "무지개빛 꼬리를 가진 신비한 여우",           "rarity": "unique",    "unlock_level": 3},

    {"name": "우주거북",     "category": "character", "price": 24, "emoji": "✨",
     "image_url": "cosmic_turtle.png",
     "description": "등껍질에 은하가 담긴 신비한 거북",           "rarity": "unique",    "unlock_level": 3},

    {"name": "별자리양",     "category": "character", "price": 24, "emoji": "⭐",
     "image_url": "constellation_sheep.png",
     "description": "별자리가 새겨진 황금뿔의 잠자는 양",         "rarity": "unique",    "unlock_level": 4},

    # === 픽셀 아트 캐릭터 (image_url에 'pixel' 포함 → 프론트 픽셀 보존 렌더링) ===
    {"name": "얼음여우",     "category": "character", "price": 18, "emoji": "🦊",
     "image_url": "ice_fox_pixel.png",
     "description": "얼음 결정을 두른 신비로운 픽셀 여우",        "rarity": "rare",      "unlock_level": 2},

    # === Epic (Lv.5) ===
    {"name": "불꽃다이노",   "category": "character", "price": 30, "emoji": "🦖",
     "image_url": "flame_dino.png",
     "description": "불꽃 갑옷을 두른 전설의 아기 공룡",          "rarity": "epic",      "unlock_level": 5},
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
    else:
        # 기존 데이터가 있어도 image_url 업데이트 (이전 버전 호환)
        updated = 0
        for item_data in SHOP_ITEMS:
            existing = db.query(ShopItem).filter(ShopItem.name == item_data["name"]).first()
            if existing and not existing.image_url:
                existing.image_url = item_data.get("image_url", "")
                updated += 1
        if updated:
            db.commit()
            print(f"[SEED] 기존 {updated}개 아이템의 image_url 업데이트 완료")

    db.close()


if __name__ == "__main__":
    seed_database()
    print("데이터베이스 시드 완료!")
