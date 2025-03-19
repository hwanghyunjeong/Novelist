import streamlit as st
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# Gemini API 키 설정
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

# 페이지 설정
st.set_page_config(
    page_title="Gemini 이미지 생성 테스트", page_icon="🎨", layout="wide"
)

# 제목
st.title("🎨 Gemini 이미지 생성 테스트 (공식 예제)")

# 사용자 입력 받기
user_prompt = st.text_area(
    "이미지 생성을 위한 프롬프트를 입력하세요:",
    height=100,
    placeholder="예: Create a 3d rendered image of a pig with wings and a top hat flying over a happy futuristic scifi city with lots of greenery",
)

# 이미지 생성 버튼
if st.button("이미지 생성"):
    if user_prompt:
        with st.spinner("이미지를 생성하는 중..."):
            try:
                # 디버깅 정보 표시
                st.write("프롬프트:", user_prompt)

                # 공식 예제 코드로 이미지 생성
                response = client.models.generate_content(
                    model="gemini-2.0-flash-exp-image-generation",
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        response_modalities=["Text", "Image"]
                    ),
                )

                # 응답 처리
                for part in response.candidates[0].content.parts:
                    if part.text is not None:
                        st.write("텍스트 응답:", part.text)
                    elif part.inline_data is not None:
                        # PIL Image로 변환
                        image = Image.open(BytesIO(part.inline_data.data))
                        # Streamlit에 이미지 표시
                        st.image(image, caption="생성된 이미지", use_column_width=True)
                        st.success("이미지가 성공적으로 생성되었습니다!")

                        # 이미지 저장 (선택사항)
                        image.save("gemini-generated-image.png")
                        st.write(
                            "이미지가 'gemini-generated-image.png'로 저장되었습니다."
                        )

            except Exception as e:
                st.error(f"이미지 생성 중 오류 발생: {str(e)}")
                st.write("상세 오류:", e)
    else:
        st.warning("프롬프트를 입력해주세요.")

# 사이드바에 설명 추가
with st.sidebar:
    st.header("테스트 안내")
    st.markdown(
        """
    이 테스트 페이지는 Gemini API의 공식 이미지 생성 예제를 사용합니다.
    
    ### 사용 방법
    1. 텍스트 영역에 이미지 생성 프롬프트를 입력합니다.
    2. '이미지 생성' 버튼을 클릭합니다.
    3. 생성된 이미지가 화면에 표시됩니다.
    
    ### 테스트용 프롬프트 예시
    - Create a 3d rendered image of a pig with wings and a top hat flying over a happy futuristic scifi city with lots of greenery
    - Draw a simple house with a garden
    - Create a basic landscape with mountains and a lake
    """
    )
