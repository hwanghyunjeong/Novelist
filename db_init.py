# db_init.py
import os
from dotenv import load_dotenv
from db_factory import get_db_manager
import config
from db_utils import (
    load_json_data,
    create_character_node,
    create_map_node,
    create_scene_node,
    create_scene_beat_node,
    create_relationship,
    clear_database,
)

# 필요한 파일 경로
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INITIAL_DATA_DIR = os.path.join(SCRIPT_DIR, "data", "initial_data")
CHARACTER_FILE_PATH = os.path.join(INITIAL_DATA_DIR, "initial_characters.json")
MAP_FILE_PATH = os.path.join(INITIAL_DATA_DIR, "initial_maps.json")
SCENE_FILE_PATH = os.path.join(INITIAL_DATA_DIR, "initial_scenes.json")


def init_database():
    """데이터베이스 초기화 및 기본 데이터 생성"""
    load_dotenv()

    try:
        print("데이터베이스 연결 시도 중...")
        db_manager = get_db_manager(
            manager_type="langchain",
            uri=config.NEO4J_URI,
            user=config.NEO4J_USER,
            password=config.NEO4J_PASSWORD,
            database=config.NEO4J_DATABASE,
        )
        print("데이터베이스 연결 성공")

        print("기존 데이터 삭제 중...")
        clear_database(db_manager)
        print("기존 데이터 삭제 완료")

        print("초기 데이터 로드 중...")
        characters = load_json_data(CHARACTER_FILE_PATH)
        maps = load_json_data(MAP_FILE_PATH)
        scenes = load_json_data(SCENE_FILE_PATH)
        print("초기 데이터 로드 완료")

        print("캐릭터 노드 생성 중...")
        for character in characters:
            create_character_node(db_manager, character)
        print("캐릭터 노드 생성 완료")

        print("맵 노드 생성 중...")
        for map_data in maps:
            create_map_node(db_manager, map_data)
        print("맵 노드 생성 완료")

        print("씬 데이터 초기화 중...")
        for scene_data in scenes:
            if isinstance(scene_data, dict):
                # Scene 노드 생성
                create_scene_node(db_manager, scene_data)

                # Scene Beat 노드 생성 및 관계 설정
                for scene_beat_data in scene_data.get("scene_beats", []):
                    create_scene_beat_node(db_manager, scene_beat_data)
                    create_relationship(
                        db_manager, scene_beat_data["id"], scene_data["id"], "PART_OF"
                    )

                    # 다음 Scene Beat와의 관계 설정
                    for next_scene_beat_id in scene_beat_data.get(
                        "next_scene_beats", []
                    ):
                        create_relationship(
                            db_manager,
                            scene_beat_data["id"],
                            next_scene_beat_id,
                            "NEXT",
                        )

                    # 추가: conditions 정보를 관계로 저장
                    if "conditions" in scene_beat_data:
                        for action, next_beat in scene_beat_data["conditions"].items():
                            create_relationship(
                                db_manager,
                                scene_beat_data["id"],
                                next_beat,
                                "CONDITION",
                                {"action": action},
                            )

                # Map과의 관계 설정 (map 키가 있는 경우에만)
                if "map" in scene_data:
                    create_relationship(
                        db_manager,
                        scene_data["id"],
                        scene_data["map"],
                        "TAKES_PLACE_IN",
                    )
                else:
                    print(
                        f"Warning: scene_data with id {scene_data['id']} has no 'map' key"
                    )

            # scene_data가 딕셔너리가 아닌 경우도 처리
            else:
                print(f"Warning: Skipping invalid scene data: {scene_data}")

        # 추가: SceneBeat 노드 처리 (scene_beats 배열 외부에 있는 경우)
        for scene_data in scenes:
            if isinstance(scene_data, dict) and scene_data["id"].startswith(
                "scenebeat:"
            ):
                # SceneBeat 노드 생성
                create_scene_beat_node(db_manager, scene_data)

                # Conditions 정보를 관계로 저장
                if "conditions" in scene_data:
                    for action, next_beat in scene_data["conditions"].items():
                        create_relationship(
                            db_manager,
                            scene_data["id"],
                            next_beat,
                            "CONDITION",
                            {"action": action},
                        )

        print("씬 데이터 초기화 완료")

        print("데이터베이스 초기화가 성공적으로 완료되었습니다.")

    except Exception as e:
        print(f"데이터베이스 초기화 중 오류 발생: {e}")
        raise
    finally:
        if "db_manager" in locals():
            db_manager.close()


if __name__ == "__main__":
    init_database()
