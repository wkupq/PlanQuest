"""
신규 캐릭터 6마리 증분 추가 — wipe 없이 DB 에 그냥 더함.
이미 있는 image_url 은 스킵.

사용법:
  cd backend
  python add_new_chars.py
"""
from database import SessionLocal
from models import ShopItem


NEW_CHARS = [
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


def main():
    db = SessionLocal()
    try:
        added, skipped = 0, 0
        for char in NEW_CHARS:
            existing = db.query(ShopItem).filter_by(image_url=char["image_url"]).first()
            if existing:
                print(f"  ⏭️  스킵: {char['name']} (이미 있음)")
                skipped += 1
                continue
            db.add(ShopItem(**char))
            added += 1
            print(f"  ✅ 추가: {char['emoji']} {char['name']} ({char['price']}H · {char['rarity']})")
        db.commit()
        print(f"\n총 {added}개 추가, {skipped}개 스킵.")

        # 전체 등급 분포
        from collections import Counter
        rows = db.query(ShopItem).filter_by(category="character").all()
        c = Counter(r.rarity for r in rows)
        print(f"\n현재 등급 분포 (총 {len(rows)}마리):")
        for rarity in ["common", "rare", "unique", "epic", "legendary"]:
            if c.get(rarity):
                print(f"  {rarity}: {c[rarity]}마리")
    finally:
        db.close()


if __name__ == "__main__":
    main()
