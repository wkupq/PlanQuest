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


# starter 캐릭터 8마리 (4마리 + 신규 4마리).
NEW_SHOP_ITEMS = [
    # ─── 기존 4마리 ───
    {"name": "불꽃포메", "category": "character", "price": 6, "emoji": "🔥",
     "image_url": "flame_pom.png",
     "description": "머리에 불꽃을 단 통통한 포메라니안",
     "rarity": "common", "unlock_level": 1},

    {"name": "달빛토끼", "category": "character", "price": 8, "emoji": "🌙",
     "image_url": "moon_bunny.png",
     "description": "이마에 황금 초승달이 빛나는 토끼",
     "rarity": "common", "unlock_level": 1},

    {"name": "눈구름냥", "category": "character", "price": 8, "emoji": "❄️",
     "image_url": "snow_cat.png",
     "description": "구름 같은 꼬리에 솜털 갈기 가진 흰 고양이",
     "rarity": "common", "unlock_level": 1},

    {"name": "우주거북", "category": "character", "price": 24, "emoji": "✨",
     "image_url": "cosmic_turtle.png",
     "description": "등껍질에 은하가 담긴 신비한 거북 — 시간당 하트 많이 줌",
     "rarity": "unique", "unlock_level": 3},

    # ─── 신규 4마리 ───
    {"name": "알파카", "category": "character", "price": 10, "emoji": "🦙",
     "image_url": "alpaca.png",
     "description": "컬러풀한 술 장식을 한 친근한 알파카",
     "rarity": "common", "unlock_level": 1},

    {"name": "카피바라", "category": "character", "price": 8, "emoji": "🦦",
     "image_url": "capybara.png",
     "description": "느긋한 표정의 통통한 카피바라",
     "rarity": "common", "unlock_level": 1},

    {"name": "소나무", "category": "character", "price": 14, "emoji": "🌲",
     "image_url": "mystic_tree.png",
     "description": "푸른 잎이 무성한 소나무",
     "rarity": "rare", "unlock_level": 2},

    {"name": "파파야나무", "category": "character", "price": 12, "emoji": "🌴",
     "image_url": "papaya_tree.png",
     "description": "잘 익은 파파야 열매가 달린 열대 나무",
     "rarity": "common", "unlock_level": 2},

    # ─── 신규 6마리 ───
    {"name": "불꽃펭귄", "category": "character", "price": 10, "emoji": "🐧",
     "image_url": "flame_penguin.png",
     "description": "머리에 작은 불꽃을 얹은 아기 펭귄",
     "rarity": "common", "unlock_level": 1},

    {"name": "호랑햄스터", "category": "character", "price": 8, "emoji": "🐹",
     "image_url": "tiger_hamster.png",
     "description": "호랑이 줄무늬가 매력적인 통통한 햄스터",
     "rarity": "common", "unlock_level": 1},

    {"name": "음악수달", "category": "character", "price": 14, "emoji": "🎧",
     "image_url": "music_otter.png",
     "description": "헤드폰을 쓰고 조개 가방을 멘 수달",
     "rarity": "rare", "unlock_level": 2},

    {"name": "무지개여우", "category": "character", "price": 20, "emoji": "🌈",
     "image_url": "rainbow_fox.png",
     "description": "무지개빛 꼬리를 가진 신비한 여우",
     "rarity": "unique", "unlock_level": 3},

    {"name": "별자리양", "category": "character", "price": 24, "emoji": "⭐",
     "image_url": "constellation_sheep.png",
     "description": "별자리가 새겨진 황금뿔의 잠자는 양",
     "rarity": "unique", "unlock_level": 4},

    {"name": "라벤더냥", "category": "character", "price": 12, "emoji": "💜",
     "image_url": "lavender_cat.png",
     "description": "이마에 별이 빛나는 라벤더빛 고양이",
     "rarity": "rare", "unlock_level": 2},
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
