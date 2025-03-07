# config.py
import os
from dotenv import load_dotenv

# .env 파일 체크 및 로드 (중복호출 방지)
env_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(env_file_path):
    load_dotenv(dotenv_path=env_file_path)
    print("환경변수가 로드되었습니다.")
else:
    print("환경변수가 존재하지 않습니다.")

# 환경 변수 설정
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

# 필수 환경 변수 체크
required_keys = [
    "OPENAI_API_KEY",
    "GOOGLE_API_KEY",
    "NEO4J_URI",
    "NEO4J_USER",
    "NEO4J_PASSWORD",
]
for key in required_keys:
    if not os.getenv(key):
        raise ValueError(f"{key} is not set in .env file")
