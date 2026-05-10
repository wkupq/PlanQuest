"""
상점/배치/보유 전부 wipe + 새 starter 만 등록.

기존 ShopItem 전체 + OwnedItem (구매 기록) + PlacedItem (배치) 모두 정리.
새 픽셀 아트 여우만 starter 로 추가.

사용법:
  cd backend
  python reset_shop.py
"""
from database import SessionLocal, engine, Base
from models import ShopItem, OwnedItem, PlacedItem


# 새 starter 캐릭터 4마리.
# image_url 에 'pixel' 단어 들어가면 프론트가 image-rendering: pixelated 적용.
NEW_SHOP_ITEMS = [
    {
        "name": "불꽃포메",
        "category": "character",
        "price": 3,
        "emoji": "🔥",
        "image_url": "flame_pom.png",
        "description": "머리에 불꽃을 단 통통한 포메라니안",
        "rarity": "common",
        "unlock_level": 1,
    },
    {
        "name": "달빛토끼",
        "category": "character",
        "price": 4,
        "emoji": "🌙",
        "image_url": "moon_bunny.png",
        "description": "이마에 황금 초승달이 빛나는 토끼",
        "rarity": "common",
        "unlock_level": 1,
    },
    {
        "name": "눈구름냥",
        "category": "character",
        "price": 4,
        "emoji": "❄️",
        "image_url": "snow_cat.png",
        "description": "구름 같은 꼬리에 솜털 갈기 가진 흰 고양이",
        "rarity": "common",
        "unlock_level": 1,
    },
    {
        "name": "우주거북",
        "category": "character",
        "price": 8,
        "emoji": "✨",
        "image_url": "cosmic_turtle.png",
        "description": "등껍질에 은하가 담긴 신비한 거북",
        "rarity": "rare",
        "unlock_level": 3,
    },
]


def reset():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # 1) 통계
    n_shop = db.query(ShopItem).count()
    n_owned = db.query(OwnedItem).count()
    n_placed = db.query(PlacedItem).count()
    print(f"[현재] 상점={n_shop}, 보유={n_owned}, 배치={n_placed}")

    # 2) FK 의존성 순서대로 삭제
    db.query(PlacedItem).delete()
    db.query(OwnedItem).delete()
    db.query(ShopItem).delete()
    db.commit()
    print(f"[삭제] 배치/보유/상점 모두 정리")

    # 3) 새 starter 만 등록
    for item in NEW_SHOP_ITEMS:
        db.add(ShopItem(**item))
    db.commit()
    print(f"[추가] 새 starter {len(NEW_SHOP_ITEMS)}개")

    # 4) 결과
    print("\n새 상점 구성:")
    for it in db.query(ShopItem).all():
        print(f"  - {it.emoji} {it.name:12s} ({it.image_url:25s}) {it.price}H Lv.{it.unlock_level}")

    db.close()
    print("\n완료. 백엔드 재시작 + 브라우저 새로고침.")


if __name__ == "__main__":
    reset()
