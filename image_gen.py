from langchain.prompts import PromptTemplate
from google import genai
from google.genai import types
import os
from dotenv import load_dotenv
from typing import Optional

# .env 파일 로드
load_dotenv()

# Gemini API 키 설정
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Gemini 클라이언트 생성
client = genai.Client(api_key=GEMINI_API_KEY)

# 이미지 생성을 위한 프롬프트 템플릿 정의
IMAGE_PROMPT_TEMPLATE = PromptTemplate(
    input_variables=["summary", "current_scene"],
    template="""Create a detailed art image of a post-apocalyptic graphic novel.

Setting Context:
{summary}

Current Location: {current_scene}

Style Requirements:
- Digital art style
- Dark and moody atmosphere
- Destroyed urban environment
- Cinematic lighting
- Detailed architectural elements
- Focus on the subway station infrastructure
- Include signs of destruction and abandonment
- Maintain Korean architectural elements

The image should effectively convey the post-apocalyptic atmosphere while preserving recognizable elements of a scene.""",
)


def generate_scene_image(summary: str, current_scene: str) -> Optional[bytes]:
    """이미지 프롬프트 템플릿을 사용하여 현재 씬에 대한 이미지를 생성합니다."""
    # 프롬프트 템플릿으로 이미지 프롬프트 생성
    image_prompt = IMAGE_PROMPT_TEMPLATE.format(
        summary=summary, current_scene=current_scene
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=image_prompt,
            config=types.GenerateContentConfig(response_modalities=["Text", "Image"]),
        )

        if response.image:
            return response.image.image_bytes
        else:
            print("No image generated in response")
            return None

    except Exception as e:
        print(f"이미지 생성 실패: {e}")
        return None
