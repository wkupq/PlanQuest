"""
캐릭터 이름 변경 — 기존 DB 의 ShopItem name/emoji/description 만 UPDATE.
OwnedItem, PlacedItem 은 shop_item_id 로 연결돼 있어서 보유/배치 영향 X.

사용법:
  cd backend
  python rename_chars.py
"""
from database import SessionLocal
from models import ShopItem


# image_url 기준으로 매핑 (name 이 바뀌어도 PNG 파일명은 그대로)
RENAMES = {
    "alpaca.png": {
        "name": "알파카",
        "emoji": "🦙",
        "description": "컬러풀한 술 장식을 한 친근한 알파카",
    },
    "mystic_tree.png": {
        "name": "소나무",
        "emoji": "🌲",
        "description": "푸른 잎이 무성한 소나무",
    },
}


def main():
    db = SessionLocal()
    try:
        changed = 0
        for image_url, new_data in RENAMES.items():
            item = db.query(ShopItem).filter_by(image_url=image_url).first()
            if not item:
                print(f"  ⚠️ {image_url}: 상점에 없음 (스킵)")
                continue

            old_name = item.name
            for k, v in new_data.items():
                setattr(item, k, v)
            changed += 1
            print(f"  ✅ {old_name} → {item.name}")

        if changed:
            db.commit()
            print(f"\n총 {changed}개 캐릭터 이름 변경됨.")
        else:
            print("\n변경할 항목 없음.")

        # 현재 상태 출력
        print("\n현재 character 상점:")
        for it in db.query(ShopItem).filter_by(category="character").all():
            print(f"  {it.emoji} {it.name:10s} ({it.image_url}) {it.price}H Lv.{it.unlock_level}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
