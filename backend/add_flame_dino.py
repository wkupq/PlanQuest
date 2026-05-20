"""
사용자 DB(~/habit_forest.db)에 불꽃공룡을 직접 추가.
seed_database() 는 DB 비었을 때만 동작하므로, 이미 다른 아이템이 있으면 별도로 추가해야 함.

사용법:
  cd backend
  python add_flame_dino.py
"""
from database import SessionLocal, engine, Base
from models import ShopItem

Base.metadata.create_all(bind=engine)
db = SessionLocal()

# 이미 있는지 확인
existing = db.query(ShopItem).filter_by(image_url="flame_dino.png").first()
if existing:
    print(f"[이미 있음] id={existing.id} name={existing.name}")
else:
    item = ShopItem(
        name="불꽃공룡",
        category="character",
        price=3,
        emoji="🦖",
        image_url="flame_dino.png",
        description="머리에 불꽃 왕관을 쓴 아기 공룡",
        rarity="common",
        unlock_level=1,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    print(f"[추가됨] id={item.id} {item.name} ({item.image_url})")

# 현재 DB 의 character 카테고리 전체 출력 (확인용)
print("\n현재 character 아이템 목록:")
chars = db.query(ShopItem).filter_by(category="character").all()
for it in chars:
    img = it.image_url if it.image_url else "(이미지없음)"
    print(f"  id={it.id:3d} {it.name:15s} {it.price}H Lv.{it.unlock_level} - {img}")

db.close()
print("\n완료. 이제 백엔드 재시작 + 브라우저 새로고침 → 상점에서 '불꽃공룡' 확인하세요.")
