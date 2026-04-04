"""Plan-Quest - FastAPI 백엔드 메인"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine, Base
from seed_data import seed_database

from routers import user, habits, trees, shop, placement

# DB 초기화 + 시드
Base.metadata.create_all(bind=engine)
seed_database()

app = FastAPI(title="Plan-Quest API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(user.router)
app.include_router(habits.router)
app.include_router(trees.router)
app.include_router(shop.router)
app.include_router(placement.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=True)
