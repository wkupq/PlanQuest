import yaml
import os

CONFIG_PATH = "config.yaml"

def load_config() -> dict:
    """config.yaml 불러오기"""
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"config.yaml 없음 -> setup_security.py 먼저 실행하세요")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def get_bm25_path() -> str:
    """BM25 인덱스 경로 가져오기"""
    try:
        config = load_config()
        return config["paths"]["bm25_index"]
    except (KeyError, FileNotFoundError):
        return "bm25_index.pkl"  # 기본값

def get_chroma_path() -> str:
    """ChromaDB 경로 가져오기"""
    try:
        config = load_config()
        return config["paths"]["chroma_db"]
    except (KeyError, FileNotFoundError):
        return "./chroma_db"  # 기본값

def get_db_path() -> str:
    """DB 경로 가져오기"""
    try:
        config = load_config()
        return config["db"]["path"]
    except (KeyError, FileNotFoundError):
        return "assistant.db"  # 기본값