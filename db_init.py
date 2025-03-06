# db_init.py
import os
from db import DBManager
from db_utils import (
    load_json_data,
    create_character_node,
    create_map_node,
    create_scene_node,
    create_scene_beat_node,
    create_relationship,
)

# 필요한 파일 경로
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INITIAL_DATA_DIR = os.path.join(SCRIPT_DIR, "data", "initial_data")
CHARACTER_FILE_PATH = os.path.join(INITIAL_DATA_DIR, "initial_characters.json")
MAP_FILE_PATH = os.path.join(INITIAL_DATA_DIR, "initial_maps.json")
SCENE_FILE_PATH = os.path.join(INITIAL_DATA_DIR, "initial_scenes.json")


def initialize_db(tx):
    """Neo4j 데이터베이스를 초기화합니다."""
    characters = load_json_data(CHARACTER_FILE_PATH)
    maps = load_json_data(MAP_FILE_PATH)
    scenes = load_json_data(SCENE_FILE_PATH)

    # 캐릭터 노드 생성
    for character in characters:
        create_character_node(tx, character)

    # 맵 노드 생성
    for map_data in maps:
        create_map_node(tx, map_data)

    # 씬 노드 및 관계 생성
    initialize_scene_data(tx, scenes)

    print("Neo4j 데이터베이스 초기화 완료")


def initialize_scene_data(tx, scenes):
    """씬 관련 데이터 초기화"""
    for scene in scenes:
        create_scene_node(tx, scene)
        for scene_beat in scene.get("scene_beats", []):
            create_scene_beat_node(tx, scene_beat)
            create_relationship(tx, scene_beat["id"], scene["id"], "PART_OF")
            for next_scene_beat_id in scene_beat.get("next_scene_beats", []):
                create_relationship(tx, scene_beat["id"], next_scene_beat_id, "NEXT")
        create_relationship(tx, scene["id"], scene["map"], "TAKES_PLACE_IN")


if __name__ == "__main__":
    db_manager = DBManager(
        uri="bolt://localhost:7687", user="neo4j", password="11111111"
    )
    try:
        with db_manager.driver.session() as session:
            session.execute_write(initialize_db)
    finally:
        db_manager.close()
