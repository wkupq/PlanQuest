# 📦 Plan-Quest 패키징 가이드 (PyInstaller)

> **팀 D 담당** — PyInstaller `.exe` 빌드 + 의존성 충돌 해결.
> 최종 배포물: `dist/PlanQuest/PlanQuest.exe` 더블클릭으로 게임 실행 가능.

---

## 🚀 한 줄 빌드

```powershell
cd backend
.\build.ps1
```

또는 cmd:
```cmd
cd backend
build.bat
```

성공 시: `backend/dist/PlanQuest/PlanQuest.exe` 생성.

---

## 📁 빌드 결과물

```
backend/dist/PlanQuest/
├── PlanQuest.exe          ← 더블클릭으로 실행
├── _internal/
│   ├── ... (Python 런타임 + 의존성)
│   ├── chromadb/          (벡터 DB)
│   ├── langchain/         (AI 에이전트)
│   └── frontend_build/    (React 정적 파일 — 같이 패키징됐을 때)
└── (필요 시 .dll 들)
```

전체 크기: **약 500~700 MB** (langchain + chromadb + onnxruntime 합산).

---

## 🔧 빌드 단계 (자동화 스크립트가 하는 일)

1. **PyInstaller 설치 확인** (`pip install pyinstaller`)
2. **프론트엔드 빌드** (`cd frontend && npm run build`)
3. **이전 dist/build 정리**
4. **`pyinstaller plan_quest.spec --clean --noconfirm`**

---

## ⚙️ 빌드 옵션

### 프론트 스킵 (백엔드만 빌드)
```powershell
.\build.ps1 --skip-frontend
```

이 경우 게임 UI 는 별도로 `npm start` 로 실행해야 함.

### 콘솔 창 없이 (배포용)
`plan_quest.spec` 의 `console=True` 를 `False` 로 변경 후 재빌드. 단, 로그가 안 보이니 디버깅 시엔 True 유지.

### 단일 .exe (onefile)
spec 의 `EXE(...)` 부분에 `exclude_binaries=False` 로 변경. 다만 실행 속도가 매우 느려짐 (실행 시마다 압축 해제). **onedir 권장**.

---

## ⚠️ 흔한 의존성 충돌과 해결

### 1) `ModuleNotFoundError: No module named 'langchain_core'`
**원인**: PyInstaller 가 동적 import 를 못 잡음.
**해결**: spec 의 `hidden` 리스트에 이미 `collect_submodules('langchain_core')` 포함됨. 추가 모듈 필요하면:
```python
hidden += ['langchain_core.runnables.base', 'langchain_core.callbacks']
```

### 2) `ImportError: DLL load failed (onnxruntime)`
**원인**: onnxruntime 의 native .dll 이 누락.
**해결**: spec 의 `binaries` 에 이미 `collect_dynamic_libs('onnxruntime')` 포함됨. 그래도 안 되면:
```powershell
# 시스템 dll 도 같이 넣어보기
pip install onnxruntime --force-reinstall
.\build.ps1
```

### 3) `sqlite3.OperationalError: no such module: ...` 또는 dialect 에러
**원인**: SQLAlchemy 의 sqlite dialect 가 빠짐.
**해결**: spec 의 `hidden` 에:
```python
'sqlalchemy.dialects.sqlite',
'sqlalchemy.dialects.sqlite.pysqlite',
'sqlalchemy.sql.default_comparator',
```
이미 포함됨.

### 4) `RuntimeError: pydantic_core compiled C ext missing`
**원인**: Pydantic v2 의 Rust 컴파일 부분이 누락.
**해결**:
```powershell
pip install --upgrade pydantic pyinstaller
.\build.ps1
```
PyInstaller 6.x 이상이면 자동 해결.

### 5) `chromadb.errors.InvalidCollectionException` 또는 schema mismatch
**원인**: PyInstaller 가 chromadb 의 SQL 스크립트 파일을 빠뜨림.
**해결**: spec 의 `datas` 에 이미 `collect_data_files('chromadb')` 포함됨. 그래도 안 되면 ChromaDB 폴더 직접 추가:
```python
datas += [(r'C:\path\to\chromadb\db\system_init.sql', 'chromadb/db')]
```

### 6) 빌드 OK 인데 실행 시 `failed to execute script main`
**원인**: 런타임 에러 (콘솔 창에 표시됨).
**해결**: spec 의 `console=True` 로 두고 .exe 실행 → 에러 메시지 확인.

### 7) 매우 큰 빌드 크기 (1GB +)
**원인**: 사용 안 하는 라이브러리도 포함됨.
**해결**: spec 의 `excludes` 에 이미 `torch`, `tensorflow`, `IPython` 등 추가됨. 더 줄이려면:
```python
excludes += ['matplotlib', 'PIL', 'scipy']  # 사용 안 하는 것
```

### 8) Windows Defender 가 차단
**원인**: PyInstaller 로 만든 .exe 는 종종 거짓 양성 탐지.
**해결**:
- 빌드 후 .exe 를 Windows Defender 예외 처리
- 또는 코드 서명 인증서 구매 (배포 시)
- 또는 `--onedir` 사용 (단일 .exe 보다 false positive 적음)

---

## 🎯 배포 체크리스트

빌드 끝난 후 사용자에게 전달하기 전:

- [ ] `dist/PlanQuest/PlanQuest.exe` 더블클릭으로 실행되는지 확인
- [ ] 브라우저에서 `http://localhost:8000` 접속 → 게임 화면 뜨는지
- [ ] 상점 → 캐릭터 구매 → 배치까지 동작 확인
- [ ] Ollama 안 켜져 있어도 슬래시 커맨드 (`/help`, `/hearts`) 동작 확인
- [ ] DB 파일 위치 확인 (`~/habit_forest.db` 자동 생성)
- [ ] 종료 시 (Ctrl+C 또는 X) graceful shutdown 동작

### 사용자에게 안내할 것
1. **PlanQuest 폴더 통째로** 전달 (.exe 단독 X)
2. **Ollama 별도 설치** 안내 (https://ollama.ai) — AI 채팅 쓰려면
3. **첫 실행 시** 데이터 폴더 생성 동의 (Windows 보안 팝업)

---

## 🐳 (선택) Docker 배포

PyInstaller 대신 Docker 로 배포하고 싶으면:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install -r requirements.txt
COPY backend ./
COPY frontend/build ./frontend_build
ENV FRONTEND_BUILD_DIR=/app/frontend_build
EXPOSE 8000
CMD ["python", "main.py"]
```

빌드 + 실행:
```powershell
docker build -t plan-quest .
docker run -p 8000:8000 -v ${HOME}:/root plan-quest
```

---

## 📝 spec 파일 수정 위치

`backend/plan_quest.spec` 의 주요 섹션:

| 섹션 | 역할 |
|------|------|
| `hidden` | hidden imports (PyInstaller 자동 감지 못 하는 것) |
| `datas` | 런타임에 읽는 데이터 파일 |
| `binaries` | .dll/.so 같은 동적 라이브러리 |
| `excludes` | 빌드에서 제외할 거대 패키지 |
| `EXE(console=...)` | True=콘솔 창 표시, False=백그라운드 |
| `icon` | .ico 파일 경로 |

수정 후 다시 `pyinstaller plan_quest.spec --clean --noconfirm`.

---

## 🔍 빌드 디버깅

빌드 자체가 실패할 때:
```powershell
pyinstaller plan_quest.spec --clean --noconfirm --log-level DEBUG > build.log 2>&1
```
`build.log` 에서 `ERROR` 검색.

빌드는 됐는데 .exe 실행 시 에러:
```powershell
.\dist\PlanQuest\PlanQuest.exe
# 콘솔 창에 traceback 출력됨 (spec 의 console=True 일 때)
```

특정 모듈 import 실패:
```powershell
# 빌드 후 import 테스트
.\dist\PlanQuest\PlanQuest.exe --check-imports
```
(이건 main.py 에 `--check-imports` 옵션 추가하면 됨 — 필요하면 작성해드릴게요)

---

## 🎯 D 역할 패키징 마무리

이 가이드를 따라 빌드하면:
- ✅ 단일 폴더로 게임 + AI 백엔드 통째 배포
- ✅ Python 미설치 PC 에서도 동작
- ✅ Ollama 만 별도 설치하면 AI 채팅까지 모두 작동
- ✅ 의존성 충돌 (langchain / chromadb / pydantic) 해결됨

D 역할 W5 패키징 완료 기준 충족.
