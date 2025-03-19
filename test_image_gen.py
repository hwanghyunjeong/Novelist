from image_gen import generate_scene_image


def test_simple_image_generation():
    """간단한 이미지 생성 테스트"""
    # 테스트용 간단한 프롬프트
    test_prompt = "Create a simple test image of a cat sitting on a windowsill"

    print("테스트 시작...")
    print("프롬프트:", test_prompt)

    # 이미지 생성 시도
    image_data = generate_scene_image(summary="test", current_scene=test_prompt)

    if image_data:
        print("이미지 생성 성공!")
        # 테스트용 이미지 저장
        with open("test_output.png", "wb") as f:
            f.write(image_data)
        print("이미지가 test_output.png로 저장되었습니다.")
    else:
        print("이미지 생성 실패")


if __name__ == "__main__":
    test_simple_image_generation()
