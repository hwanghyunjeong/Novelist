import os
import json
import re
from neo4j import GraphDatabase
from typing import List, Dict, Any
from db import DBManager, config
from db_utils import (
    create_character_node,
    create_map_node,
    create_scene_node,
    create_scene_beat_node,
    create_relationship,
    clear_database,
)


def load_data_from_file(file_path: str) -> List[Dict] | Dict | None:
    """JSON 파일 또는 기타 형식의 파일에서 데이터를 로드합니다.

    Args:
        file_path (str): 파일 경로.

    Returns:
        List[Dict] | Dict | None: 로드된 데이터.
                                  파일이 비었거나 읽을 수 없는 경우 None.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            if file_path.endswith(".json"):
                return json.load(f)
            else:
                # 텍스트 파일의 경우 각 줄을 데이터로 처리
                lines = f.readlines()
                # 비어있는 파일인 경우
                if not lines:
                    return None
                return [{"text": line.strip()} for line in lines]

    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError) as e:
        print(f"Error loading data from {file_path}: {e}")
        return None


def process_data(tx, data: List[Dict] | Dict | None, file_name: str):
    """로드된 데이터를 처리하여 Neo4j에 저장합니다.

    Args:
        tx (Transaction): Neo4j 트랜잭션.
        data (List[Dict] | Dict | None): 로드된 데이터.
        file_name (str): 파일 이름
    """
    if data is None:
        print(f"No data to process from {file_name}.")
        return

    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                _process_complex_data(tx, item, file_name)
            else:
                _create_generic_node(tx, file_name, item, file_name)
    elif isinstance(data, dict):
        # 딕셔너리 형태의 데이터 처리 (예: 단일 JSON 객체)
        _process_complex_data(tx, data, file_name)
    else:
        print(f"Unsupported data type for {file_name}.")


def initialize_scene_data(tx, scenes: List[Dict]):
    """db_init.py의 동일 함수를 가져옴."""
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


def _create_generic_node(tx, key: str, value: Any, file_name: str):
    """
    정형화 되지 않은 데이터도 수용할 수 있도록 처리하는 함수
    """
    try:
        if isinstance(value, dict):
            value = json.dumps(value, ensure_ascii=False)
        if isinstance(value, list):
            value = json.dumps(value, ensure_ascii=False)
        tx.run(
            f"""
            MERGE (n:GenericNode {{id: $id}})
            SET n.key = $key, n.value = $value, n.source = $file_name
            """,
            id=f"{file_name}_{key}_{hash(str(value))}",  # Unique ID based on file name and content snippet
            key=key,
            value=value,
            file_name=file_name,
        )
    except Exception as e:
        print(f"Error during _create_generic_node : {e}")


def _process_complex_data(tx, data: Dict, file_name: str):
    """중첩된 데이터 구조를 처리하는 함수"""
    if "story_scripts" in data:
        _create_story_script_node(tx, data["story_scripts"], file_name)
    else:
        for key, value in data.items():
            if isinstance(value, dict):
                _process_complex_data(tx, value, file_name)
            elif isinstance(value, list):
                for i in range(len(value)):
                    _create_generic_node(tx, f"{key}_{i}", value[i], file_name)
            else:
                _create_generic_node(tx, key, value, file_name)


def _create_story_script_node(tx, story_scripts: list[dict], file_name: str):
    """스토리 스크립트 노드를 생성하고 연결하는 함수"""
    try:
        for script in story_scripts:
            script_id = f"{file_name}_script_{story_scripts.index(script)}"
            tx.run(
                """
                MERGE (ss:StoryScript {id: $id})
                SET ss += $script
                """,
                id=script_id,
                script=script,
            )
            # 연관된 character, location 등에 대한 관계 생성 로직을 추가할 수 있습니다.
            if "character" in script:
                for character in script["character"]:
                    tx.run(
                        """
                        MATCH (ss:StoryScript {id: $script_id})
                        MATCH (c:Character {id: $character_id})
                        MERGE (ss)-[:HAS_CHARACTER]->(c)
                        """,
                        script_id=script_id,
                        character_id=character,
                    )

            if "location" in script:
                tx.run(
                    """
                    MATCH (ss:StoryScript {id: $script_id})
                    MERGE (l:Location {id: $location_id})
                    MERGE (ss)-[:HAS_LOCATION]->(l)
                    """,
                    script_id=script_id,
                    location_id=script["location"],
                )

    except Exception as e:
        print(f"Error during _create_story_script_node : {e}")


def import_data_to_neo4j(
    db_manager: DBManager, data_dir: str, file_pattern: str = r".*\.json$|.*\.txt$"
):
    """지정된 디렉토리에서 패턴과 일치하는 파일을 찾아 Neo4j에 데이터를 임포트합니다.

    Args:
        db_manager (DBManager): Neo4j 연결을 관리하는 DBManager 인스턴스.
        data_dir (str): 데이터 파일이 있는 디렉토리 경로.
        file_pattern (str): 파일을 찾기 위한 정규 표현식 패턴 (기본값: *.json).
    """
    try:
        with db_manager.driver.session() as session:
            session.execute_write(clear_database)
            for file_name in os.listdir(data_dir):
                if re.fullmatch(file_pattern, file_name):
                    file_path = os.path.join(data_dir, file_name)
                    print(f"Processing file: {file_path}")
                    data = load_data_from_file(file_path)
                    session.execute_write(process_data, data, file_name)
            print("Data import to Neo4j completed.")

    except Exception as e:
        print(f"Error during data import: {e}")
        raise


if __name__ == "__main__":
    db_manager = DBManager(config.NEO4J_URI, config.NEO4J_USER, config.NEO4J_PASSWORD)
    DATA_DIRECTORY = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "data", "stored_data"
    )  # data/stored_data 경로

    # Check if the directory exists, create it if not
    if not os.path.exists(DATA_DIRECTORY):
        os.makedirs(DATA_DIRECTORY)
        print(f"Directory created: {DATA_DIRECTORY}")

    try:
        import_data_to_neo4j(db_manager, DATA_DIRECTORY)
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        db_manager.close()
