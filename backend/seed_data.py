"""상점 초기 데이터 시드 - 이미지 기반 캐릭터 시스템"""
from database import engine, SessionLocal, Base
from models import ShopItem, UserProfile

# === 캐릭터 이미지 기반 상점 아이템 ===
# image_url: frontend/public/images/characters/ 폴더 안의 PNG 파일명
# 이미지를 추가하면 자동으로 상점에 표시됩니다
SHOP_ITEMS = [
    # === starter 캐릭터 (Common, Lv.1) ===
    # 픽셀 아트 캐릭터: image_url 에 'pixel' 들어가면 프론트가 픽셀 보존 렌더링.
    # 추후 캐릭터 추가 시 PNG 를 frontend/public/images/characters/ 에 두고 이 리스트에 추가.

    {"name": "불꽃포메", "category": "character", "price": 3, "emoji": "🔥",
     "image_url": "flame_pom.png",
     "description": "머리에 불꽃을 단 통통한 포메라니안",
     "rarity": "common", "unlock_level": 1},

    {"name": "달빛토끼", "category": "character", "price": 4, "emoji": "🌙",
     "image_url": "moon_bunny.png",
     "description": "이마에 황금 초승달이 빛나는 토끼",
     "rarity": "common", "unlock_level": 1},

    {"name": "눈구름냥", "category": "character", "price": 4, "emoji": "❄️",
     "image_url": "snow_cat.png",
     "description": "구름 같은 꼬리에 솜털 갈기 가진 흰 고양이",
     "rarity": "common", "unlock_level": 1},

    {"name": "우주거북", "category": "character", "price": 8, "emoji": "✨",
     "image_url": "cosmic_turtle.png",
     "description": "등껍질에 은하가 담긴 신비한 거북",
     "rarity": "rare", "unlock_level": 3},
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
