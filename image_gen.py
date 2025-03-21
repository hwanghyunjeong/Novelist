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


# 한글 텍스트를 영문으로 번역하고 요약하는 함수
def translate_and_summarize(text: str, max_words: int = 50) -> str:
    """
    한글 텍스트를 영문으로 번역하고 요약합니다.

    Args:
        text: 번역 및 요약할 한글 텍스트
        max_words: 요약된 영문 텍스트의 최대 단어 수

    Returns:
        번역 및 요약된 영문 텍스트
    """
    try:
        if not text:
            return ""

        # 번역 및 요약 프롬프트
        prompt = f"""
        Translate the following Korean text to English and summarize it within {max_words} words. 
        Focus on the visual elements, mood, setting, and atmosphere that would be useful for generating an image.
        
        Korean text: {text}
        
        English translation and summary:
        """

        # Gemini 모델을 사용하여 번역 및 요약
        response = client.models.generate_content(
            model="gemini-2.0-flash", contents=prompt
        )

        # 응답에서 텍스트 추출
        translated_summary = response.text.strip()
        return translated_summary

    except Exception as e:
        print(f"번역 및 요약 실패: {e}")
        # 오류 발생 시 원본 텍스트를 영어로 간단히 대체
        return "scene in dark post-apocalyptic setting"


def generate_scene_image(summary: str, current_scene: str) -> Optional[bytes]:
    """이미지 프롬프트 템플릿을 사용하여 현재 씬에 대한 이미지를 생성합니다."""
    try:
        # 한글 텍스트를 영문으로 번역하고 요약
        translated_summary = translate_and_summarize(summary, max_words=30)
        translated_scene = translate_and_summarize(current_scene, max_words=50)

        # print(f"번역된 요약: {translated_summary}")
        # print(f"번역된 장면: {translated_scene}")

        # 프롬프트를 하나의 문자열로 구성
        prompt = f"""Create a photo-realistic image of a Post-Apocalyptic films scene. 
        Dark, gritty, eerie and tense atmosphere with cinematic lighting. 
        Ultra detailed, high resolution, 8k, realistic,first person perspective,
        {translated_scene},{translated_summary},
        Digital art with photorealistic elements"""

        # Gemini 2.0 Flash 모델로 이미지 생성 API 호출
        response = client.models.generate_content(
            model="gemini-2.0-flash-exp-image-generation",
            contents=prompt,
            config=types.GenerateContentConfig(response_modalities=["Text", "Image"]),
        )

        # 응답에서 이미지 데이터 추출
        for part in response.candidates[0].content.parts:
            if part.text is not None:
                print("텍스트 응답:", part.text)
            elif part.inline_data is not None:
                return part.inline_data.data

        return None

    except Exception as e:
        print(f"이미지 생성 실패: {e}")
        return None
