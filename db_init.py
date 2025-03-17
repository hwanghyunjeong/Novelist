# db_init.py
from db_factory import get_db_manager
import config
import os
from dotenv import load_dotenv
from db import DBManager, config
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


def initialize_db(tx):
    try:
        clear_database(tx)  # Clear the database before initializing

        characters = load_json_data(CHARACTER_FILE_PATH)
        maps = load_json_data(MAP_FILE_PATH)
        scenes = load_json_data(SCENE_FILE_PATH)

        for character in characters:
            create_character_node(tx, character)
        for map_data in maps:
            create_map_node(tx, map_data)
        initialize_scene_data(tx, scenes)

        print("Neo4j 데이터베이스 초기화 완료")
    except Exception as e:
        print(
            f"데이터베이스 초기화 중 오류 발생: {e}"
        )  # rollback은 session.execute_write에서 자동으로 처리됨


def initialize_scene_data(tx, scenes):
    try:
        for scene_data in scenes:
            if isinstance(scene_data, dict):
                create_scene_node(tx, scene_data)
                for scene_beat_data in scene_data["scene_beats"]:
                    create_scene_beat_node(tx, scene_beat_data)
                    create_relationship(
                        tx, scene_beat_data["id"], scene_data["id"], "PART_OF"
                    )
                    for next_scene_beat_id in scene_beat_data.get(
                        "next_scene_beats", []
                    ):
                        create_relationship(
                            tx, scene_beat_data["id"], next_scene_beat_id, "NEXT"
                        )
                create_relationship(
                    tx, scene_data["id"], scene_data["map"], "TAKES_PLACE_IN"
                )
            else:
                print(f"WARNING: Skipping invalid scene data: {scene_data}")
    except Exception as e:
        print(f"Error initializing scene data: {e}")


def init_database():
    """데이터베이스 초기화 및 기본 데이터 생성"""
    # 환경변수 로드
    load_dotenv()

    try:
        # DB 매니저 생성
        db_manager = get_db_manager(
            manager_type="langchain",
            uri=config.NEO4J_URI,
            user=config.NEO4J_USER,
            password=config.NEO4J_PASSWORD,
            database=config.NEO4J_DATABASE,
        )

        # 기존 데이터 삭제 (필요한 경우)
        cleanup_query = """
        MATCH (n)
        DETACH DELETE n
        """
        db_manager.query(cleanup_query, {})

        # 초기 데이터 생성
        init_queries = [
            # 여기에 초기화 쿼리들을 넣습니다
            """
            CREATE (s:Scene {
                id: 'scene:00_Pangyo_Station',
                name: '판교역',
                description: '판교역 대합실'
            })
            """,
            # ... 추가 쿼리들
        ]

        for query in init_queries:
            db_manager.query(query, {})

        print("데이터베이스 초기화가 완료되었습니다.")

    except Exception as e:
        print(f"데이터베이스 초기화 중 오류 발생: {e}")
        raise
    finally:
        if db_manager:
            db_manager.close()


if __name__ == "__main__":
    init_database()
