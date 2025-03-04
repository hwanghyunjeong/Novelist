# db_init.py
import json
import os
from neo4j import GraphDatabase
from db import DBManager

# 필요한 파일 경로
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INITIAL_DATA_DIR = os.path.join(SCRIPT_DIR, "data", "initial_data")
CHARACTER_FILE_PATH = os.path.join(INITIAL_DATA_DIR, "characters.json")
MAP_FILE_PATH = os.path.join(INITIAL_DATA_DIR, "maps.json")
SCENE_FILE_PATH = os.path.join(INITIAL_DATA_DIR, "scenes.json")


def load_json_data(file_path: str):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def create_character_nodes(tx, character: dict):
    """Character 노드를 생성합니다."""
    tx.run(
        """
        MERGE (c:Character {id: $id})
        SET c += $properties
        """,
        id=character["id"],
        properties={k: v for k, v in character.items() if k != "id"},
    )
    # Character의 위치 정보 처리
    if "position" in character:
        position = character["position"]
        location_id = (
            f"characterLocation:{position['map']}-{position['x']}-{position['y']}"
        )
        tx.run(
            """
            MERGE (l:CharacterLocation {id: $location_id})
            SET l.map = $map, l.x = $x, l.y = $y
            """,
            location_id=location_id,
            map=position["map"],
            x=position["x"],
            y=position["y"],
        )
        tx.run(
            """
            MATCH (c:Character {id: $character_id}), (l:CharacterLocation {id: $location_id})
            MERGE (c)-[:LOCATED_IN]->(l)
            """,
            character_id=character["id"],
            location_id=location_id,
        )


def create_map_node(tx, map_data: dict):
    """Map 노드를 생성하고 Location 노드와 연결합니다."""
    tx.run(
        """
        MERGE (m:Map {id: $id})
        SET m += $properties
        """,
        id=map_data["id"],
        properties={k: v for k, v in map_data.items() if k != "id"},
    )
    if "characterLocations" in map_data:
        for location in map_data["characterLocations"]:
            location_id = (
                f"characterLocation:{map_data['id']}-{location['x']}-{location['y']}"
            )
            tx.run(
                """
            MERGE (l:CharacterLocation {id: $location_id})
            SET l.x = $x, l.y = $y, l.map = $map_id
            """,
                location_id=location_id,
                x=location["x"],
                y=location["y"],
                map_id=map_data["id"],
            )
            tx.run(
                """
          MATCH (m:Map {id:$map_id}), (l:CharacterLocation {id:$location_id})
          MERGE (m)-[:CONTAINS]->(l)
          """,
                map_id=map_data["id"],
                location_id=location_id,
            )


def create_scene_nodes_and_relationships(tx, scene: dict):
    """Scene 노드를 생성하고, SceneBeat 노드와 관계를 생성합니다."""
    tx.run(
        """
        MERGE (s:Scene {id: $id})
        SET s += $properties
        """,
        id=scene["id"],
        properties={
            k: v for k, v in scene.items() if k not in ["id", "scene_beats", "map"]
        },
    )

    for scene_beat in scene.get("scene_beats", []):
        tx.run(
            """
            MERGE (sb:SceneBeat {id: $id})
            SET sb += $properties
            """,
            id=scene_beat["id"],
            properties={k: v for k, v in scene_beat.items() if k != "id"},
        )
        tx.run(
            """
            MATCH (sb:SceneBeat {id: $scene_beat_id}), (s:Scene {id: $scene_id})
            MERGE (sb)-[:PART_OF]->(s)
            """,
            scene_beat_id=scene_beat["id"],
            scene_id=scene["id"],
        )
        for next_scene_beat_id in scene_beat.get("next_scene_beats", []):
            tx.run(
                """
                MATCH (sb1:SceneBeat {id: $scene_beat_id}), (sb2)
                WHERE sb2.id = $next_scene_beat_id OR sb2.id = $next_scene_id
                MERGE (sb1)-[:NEXT]->(sb2)
                """,
                scene_beat_id=scene_beat["id"],
                next_scene_beat_id=next_scene_beat_id,
                next_scene_id=next_scene_beat_id,
            )
    tx.run(
        """
        MATCH (s:Scene {id: $scene_id}), (m:Map {id: $map_id})
        MERGE (s)-[:TAKES_PLACE_IN]->(m)
        """,
        scene_id=scene["id"],
        map_id=scene["map"],
    )


def initialize_db(tx):
    """
    Neo4j 데이터베이스를 초기화합니다.
    """

    characters = load_json_data(CHARACTER_FILE_PATH)
    maps = load_json_data(MAP_FILE_PATH)
    scenes = load_json_data(SCENE_FILE_PATH)

    # 캐릭터 노드 생성
    for character in characters:
        create_character_nodes(tx, character)

    # 맵 노드 생성
    for map_data in maps:
        create_map_node(tx, map_data)

    # 씬 노드 및 관계 생성
    for scene in scenes:
        create_scene_nodes_and_relationships(tx, scene)

    print("Neo4j 데이터베이스 초기화 완료")


if __name__ == "__main__":
    db_manager = DBManager(
        uri="bolt://localhost:7687", user="neo4j", password="11111111"
    )
    db_manager.driver.execute_write(initialize_db)
    db_manager.close()
