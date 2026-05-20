# -*- mode: python ; coding: utf-8 -*-
"""
Plan-Quest 백엔드 PyInstaller spec.

빌드:
  cd backend
  pyinstaller plan_quest.spec --clean --noconfirm

산출물:
  dist/PlanQuest/
    ├── PlanQuest.exe           ← 더블클릭으로 실행
    ├── _internal/              ← 의존성, 모델 데이터
    └── frontend/               ← React build (있으면 자동 포함)

D 역할 (패키징 의존성 충돌) 핵심 처리:
  - langchain  : 동적 import 가 많아 collect_submodules 로 모두 포함
  - chromadb   : C 확장 + onnxruntime + tokenizers 같이 가져옴
  - sqlalchemy : sqlite dialect 명시 (PyInstaller 가 자주 놓침)
  - tiktoken   : data files 필요 (BPE 인코딩 테이블)
  - pydantic   : v2 의 _internal 모듈 (PyInstaller 6.x 에서 OK, 5.x 면 hidden import)
"""
import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import (
    collect_submodules,
    collect_data_files,
    collect_dynamic_libs,
)

# ─── 경로 ─────────────────────────────────────────────
HERE = Path(os.getcwd())
FRONTEND_BUILD = HERE.parent / "frontend" / "build"


# ─── hidden imports (PyInstaller 가 자동 감지 못 하는 것들) ──
hidden = []

# LangChain — 동적 로딩이 많음
hidden += collect_submodules('langchain')
hidden += collect_submodules('langchain_community')
hidden += collect_submodules('langchain_core')
hidden += collect_submodules('langsmith')

# ChromaDB
hidden += collect_submodules('chromadb')
hidden += collect_submodules('onnxruntime')
hidden += collect_submodules('tokenizers')

# SQLAlchemy — dialect 들이 PyInstaller 의 정적 분석으로 안 잡힘
hidden += [
    'sqlalchemy.dialects.sqlite',
    'sqlalchemy.dialects.sqlite.pysqlite',
    'sqlalchemy.dialects.sqlite.aiosqlite',
    'sqlalchemy.sql.default_comparator',
]

# FastAPI / uvicorn / pydantic
hidden += collect_submodules('uvicorn')
hidden += collect_submodules('fastapi')
hidden += [
    'pydantic',
    'pydantic.deprecated.decorator',
    'pydantic_core',
    'email_validator',
    'anyio._backends._asyncio',
]

# tiktoken (langchain 이 토큰 계산용으로 씀)
try:
    hidden += collect_submodules('tiktoken')
except Exception:
    pass

# google api (스캐폴드 — 실제 사용 안 해도 import 가능해야)
try:
    hidden += [
        'google.auth',
        'google.oauth2',
        'googleapiclient',
        'google_auth_oauthlib',
    ]
except Exception:
    pass


# ─── data files (런타임에 읽는 파일들) ────────────────────
datas = []

# LangChain / ChromaDB / onnxruntime 의 data files
for pkg in ['langchain', 'langchain_community', 'langchain_core',
            'chromadb', 'onnxruntime', 'tokenizers', 'tiktoken',
            'pydantic', 'fastapi', 'uvicorn']:
    try:
        datas += collect_data_files(pkg)
    except Exception as e:
        print(f"[spec] {pkg} data files 수집 실패: {e}")

# 프론트엔드 build 폴더 (있으면 함께 패키징 — main.py 가 정적 서빙)
if FRONTEND_BUILD.exists():
    datas.append((str(FRONTEND_BUILD), 'frontend_build'))
    print(f"[spec] frontend/build 포함됨: {FRONTEND_BUILD}")
else:
    print(f"[spec] frontend/build 없음 — 백엔드만 패키징 (frontend 는 따로 실행)")
    print(f"        먼저 'cd frontend && npm run build' 권장")


# ─── 동적 라이브러리 (.dll/.so/.pyd) ─────────────────────
binaries = []
for pkg in ['onnxruntime', 'chromadb', 'tokenizers']:
    try:
        binaries += collect_dynamic_libs(pkg)
    except Exception:
        pass


# ─── 빌드 설정 ───────────────────────────────────────────
block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[str(HERE)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # PyTorch / TensorFlow 같은 거대 패키지 제외 (사용 안 함)
        'torch', 'tensorflow', 'jax', 'flax',
        # Jupyter / notebook 도 제외
        'IPython', 'jupyter', 'notebook',
        # 테스트 라이브러리도 제외
        'pytest', 'unittest',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PlanQuest',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,            # True: cmd 창 같이 뜸 (로그 보임 — 디버깅용)
                             # False: 백그라운드 (배포용)
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,               # 'plan_quest.ico' 추가 가능
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PlanQuest',
)
