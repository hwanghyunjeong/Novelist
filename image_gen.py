from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO
import os
from dotenv import load_dotenv
from typing import Optional

# .env 파일 로드
load_dotenv()

# Gemini API 키 설정
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Gemini 클라이언트 생성
client = genai.Client(api_key=GEMINI_API_KEY)


def generate_scene_image(summary: str, current_scene: str) -> Optional[bytes]:
    """이미지 프롬프트 템플릿을 사용하여 현재 씬에 대한 이미지를 생성합니다."""
    try:
        # 프롬프트를 하나의 문자열로 구성
        prompt = f"Create a detailed art image of a post-apocalyptic graphic novel scene. {current_scene} The scene should be set in {summary} with digital art style, dark and moody atmosphere, destroyed urban environment, cinematic lighting, and extremely detailed."

        # test2_app.py와 동일한 방식으로 API 호출
        response = client.models.generate_content(
            model="gemini-2.0-flash-exp-image-generation",
            contents=prompt,
            config=types.GenerateContentConfig(response_modalities=["Text", "Image"]),
        )

        # test2_app.py와 동일한 방식으로 응답 처리
        for part in response.candidates[0].content.parts:
            if part.text is not None:
                print("텍스트 응답:", part.text)
            elif part.inline_data is not None:
                return part.inline_data.data

        return None

    except Exception as e:
        print(f"이미지 생성 실패: {e}")
        return None
