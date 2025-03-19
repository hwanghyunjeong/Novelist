import streamlit as st
from image_gen import generate_scene_image
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 페이지 설정
st.set_page_config(page_title="이미지 생성 테스트", page_icon="🎨", layout="wide")

# 제목
st.title("🎨 Gemini 이미지 생성 테스트")

# 사용자 입력 받기
user_prompt = st.text_area(
    "이미지 생성을 위한 프롬프트를 입력하세요:",
    height=100,
    placeholder="예: 판교역 지하 2층 대합실의 황폐화된 모습을 보여주세요. 전등이 깜빡이고 있고, 벽에는 낙서가 있으며, 바닥에는 쓰레기가 흩어져 있습니다.",
)

# 이미지 생성 버튼
if st.button("이미지 생성"):
    if user_prompt:
        with st.spinner("이미지를 생성하는 중..."):
            try:
                # 이미지 생성
                image_bytes = generate_scene_image(
                    summary="post-apocalyptic subway station", current_scene=user_prompt
                )

                if image_bytes:
                    try:
                        # 이미지 표시 - use_container_width 사용
                        st.image(
                            image_bytes,
                            caption="생성된 이미지",
                            use_container_width=True,
                        )
                        st.success("이미지가 성공적으로 생성되었습니다!")
                    except Exception as img_error:
                        st.error(f"이미지 표시 중 오류: {str(img_error)}")
                else:
                    st.error("이미지 데이터를 받지 못했습니다.")
            except Exception as e:
                st.error(f"이미지 생성 중 오류 발생: {str(e)}")
                st.write("상세 오류:", e)
    else:
        st.warning("프롬프트를 입력해주세요.")

# 사이드바에 설명 추가
with st.sidebar:
    st.header("사용 방법")
    st.markdown(
        """
    1. 텍스트 영역에 이미지 생성을 위한 프롬프트를 입력합니다.
    2. '이미지 생성' 버튼을 클릭합니다.
    3. 생성된 이미지가 화면에 표시됩니다.
    
    ### 프롬프트 작성 팁
    - 구체적인 장면 묘사를 포함하세요
    - 분위기나 환경에 대한 설명을 추가하세요
    - 원하는 스타일이나 톤을 명시하세요
    """
    )
