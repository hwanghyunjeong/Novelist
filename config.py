# config.py
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 환경변수에서 값을 가져오거나, 기본값 사용
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")


# 환경변수 검증
def validate_config():
    """환경변수가 올바르게 설정되었는지 확인"""
    required_vars = {
        "NEO4J_URI": NEO4J_URI,
        "NEO4J_USER": NEO4J_USER,
        "NEO4J_PASSWORD": NEO4J_PASSWORD,
        "NEO4J_DATABASE": NEO4J_DATABASE,
    }

    missing_vars = [
        var for var, value in required_vars.items() if not value or value == "password"
    ]

    if missing_vars:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing_vars)}"
        )


# 설정 검증 실행
validate_config()


# 필수 환경 변수 체크
required_keys = [
    "OPENAI_API_KEY",
    "GOOGLE_API_KEY",
]
for key in required_keys:
    if not os.getenv(key):
        raise ValueError(f"{key} is not set in .env file")
