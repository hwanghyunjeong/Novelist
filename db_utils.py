# db_utils.py
from neo4j import GraphDatabase
from typing import Dict, Any
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
import os

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


def load_json_data(file_path: str):
    """JSON 파일로부터 데이터를 로드합니다."""
    import json

    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def create_character_node(tx, character: dict):
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
        properties={
            k: v for k, v in map_data.items() if k not in ["id", "characterLocations"]
        },
    )
    tx.run(
        """
        MATCH (m:Map {id: $id})
        SET m.map_data = $map_data, m.context = $context
        """,
        id=map_data["id"],
        map_data=map_data["map_data"],
        context=map_data["context"],
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


def create_scene_node(tx, scene: dict):
    """Scene 노드를 생성합니다."""
    tx.run(
        """
        MERGE (s:Scene {id: $id})
        SET s += $properties
        """,
        id=scene["id"],
        properties={
            k: v
            for k, v in scene.items()
            if k not in ["id", "scene_beats", "map", "context"]
        },
    )
    tx.run(
        """
        MATCH (s:Scene {id: $id})
        SET s.context = $context
        """,
        id=scene["id"],
        context=scene["context"],
    )


def create_scene_beat_node(tx, scene_beat: dict):
    """SceneBeat 노드를 생성합니다."""
    tx.run(
        """
        MERGE (sb:SceneBeat {id: $id})
        SET sb += $properties
        """,
        id=scene_beat["id"],
        properties={k: v for k, v in scene_beat.items() if k != "id"},
    )


def create_relationship(
    tx, start_node_id: str, end_node_id: str, relationship_type: str
):
    """두 노드 간의 관계를 생성합니다."""
    tx.run(
        """
        MATCH (n1 {id: $start_node_id}), (n2 {id: $end_node_id})
        MERGE (n1)-[:$relationship_type]->(n2)
        """,
        start_node_id=start_node_id,
        end_node_id=end_node_id,
        relationship_type=relationship_type,
    )


def extract_entities_and_relationships(
    user_input: str, schema: str = ""
) -> Dict[str, Any]:
    """
    사용자 입력에서 엔티티와 관계를 추출합니다.

    Args:
        user_input: 사용자 입력 텍스트.
        schema: 데이터베이스 스키마 정보 (선택적).

    Returns:
        추출된 엔티티와 관계를 담은 딕셔너리.
        예: {"nodes": [...], "relationships": [...]}
    """
    if not user_input or not isinstance(user_input, str):
        raise ValueError("유효한 사용자 입력이 필요합니다.")

    ere_prompt_template = """
    You are a top-tier algorithm designed for extracting
    information in structured formats to build a knowledge graph.

    Extract the entities (nodes) and specify their type from the following text.
    Also extract the relationships between these nodes.

    Return result as JSON using the following format:
    {{"nodes": [ {{"id": "0", "label": "Character", "properties": {{"name": "Taehoon"}} }}],
    "relationships": [{{"type": "KNOWS", "start_node_id": "0", "end_node_id": "1", "properties": {{"since": "{Player} in the office"}} }}] }}

    Use only fhe following nodes and relationships (if provided):
    {{schema}}

    Assign a unique ID (string) to each node, and reuse it to define relationships.
    Do respect the source and target node types for relationship and
    the relationship direction.

    Make sure you adhere to the following rules to produce valid JSON objects:
    - Do not return any additional information other than the JSON in it.
    - Omit any backticks around the JSON - simply output the JSON on its own.
    - The JSON object must not wrapped into a list - it is its own JSON object.
    - Property names must be enclosed in double quotes

    Input text:

    {text}
    """
    ere_prompt = PromptTemplate.from_template(ere_prompt_template)
    model = ChatOpenAI(model="gpt-4o-mini", openai_api_key=OPENAI_API_KEY)
    output_parser = JsonOutputParser()

    ere_chain = ere_prompt | model | output_parser
    try:
        result = ere_chain.invoke({"text": user_input, "schema": schema})
        # check result struct
        if not isinstance(result, dict):
            raise ValueError("Invalid output from LLM, expect dict")
        if "nodes" not in result:
            result["nodes"] = []
        if "relationships" not in result:
            result["relationships"] = []
        return result

    except Exception as e:
        raise ValueError(f"엔티티 추출 중 오류: {e}")


def update_graph_from_er(driver, er_data: Dict[str, Any]):
    """
    추출된 엔티티와 관계 데이터를 바탕으로 그래프를 업데이트합니다.

    Args:
        driver: Neo4j 드라이버.
        er_data: 추출된 엔티티와 관계를 담은 딕셔너리.
    """
    if not isinstance(er_data, dict):
        raise ValueError("유효한 엔티티/관계 데이터가 필요합니다. (딕셔너리 타입)")

    nodes = er_data.get("nodes")
    rels = er_data.get("relationships")

    if nodes is None or rels is None:
        raise ValueError("유효한 노드/관계 데이터가 없습니다.")

    try:
        with driver.session() as session:
            for node in nodes:
                session.write_transaction(_upsert_node, node)
            for rel in rels:
                session.write_transaction(_upsert_relationship, rel)
    except Exception as e:
        raise Exception(f"그래프 업데이트 중 오류 발생: {e}")


def _upsert_node(tx, node: dict):
    """
    트랜잭션 내에서 노드를 생성하거나 업데이트합니다.
    """
    label = node.get("label", "Entity")
    try:
        tx.run(
            f"""
            MERGE (n:{label} {{id: $id}})
            SET n += $properties
            """,
            id=node["id"],
            properties=node.get("properties", {}),
        )
    except Exception as e:
        raise Exception(f"노드 업데이트 중 오류 발생: {e}, node_id: {node['id']}")


def _upsert_relationship(tx, rel: dict):
    """
    트랜잭션 내에서 관계를 생성하거나 업데이트합니다.
    """
    rel_type = rel["type"]
    try:
        tx.run(
            f"""
            MATCH (a {{id: $start_id}}), (b {{id: $end_id}})
            MERGE (a)-[r:{rel_type}]->(b)
            SET r += $properties
            """,
            start_id=rel["start_node_id"],
            end_id=rel["end_node_id"],
            properties=rel.get("properties", {}),
        )
    except Exception as e:
        raise Exception(f"관계 업데이트 중 오류 발생: {e}, rel_type: {rel_type}")
