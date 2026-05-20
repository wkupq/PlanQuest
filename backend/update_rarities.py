"""
기존 DB 캐릭터의 등급 / 가격 / 설명 업데이트.
보유/배치는 유지.

사용법:
  cd backend
  python update_rarities.py
"""
from database import SessionLocal
from models import ShopItem


UPDATES = {
    "cosmic_turtle.png": {
        "rarity": "unique",
        "price": 12,
        "description": "등껍질에 은하가 담긴 신비한 거북 — 시간당 하트 많이 줌",
    },
    # 추가 unique 캐릭터 만들고 싶으면 여기 추가
}


def main():
    db = SessionLocal()
    try:
        changed = 0
        for image_url, update in UPDATES.items():
            item = db.query(ShopItem).filter_by(image_url=image_url).first()
            if not item:
                print(f"  ⚠️ {image_url}: 없음")
                continue
            for k, v in update.items():
                setattr(item, k, v)
            changed += 1
            print(f"  ✅ {item.name}: rarity={item.rarity}, price={item.price}")
        db.commit()

        print("\n현재 등급 분포:")
        from collections import Counter
        rows = db.query(ShopItem).filter_by(category="character").all()
        c = Counter(r.rarity for r in rows)
        for rarity, count in c.most_common():
            print(f"  {rarity}: {count}마리")
    finally:
        db.close()


if __name__ == "__main__":
    main()
