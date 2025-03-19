# db_utils.py
from neo4j import GraphDatabase
from typing import Dict, Any, List
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
import os
from db_interface import DBInterface
import json

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


def clear_database(db_manager: DBInterface) -> None:
    """데이터베이스의 모든 노드와 관계를 삭제합니다."""
    query = """
    MATCH (n)
    DETACH DELETE n
    """
    db_manager.query(query=query, params={})


def load_json_data(file_path: str) -> List[Dict[str, Any]]:
    """JSON 파일에서 데이터를 로드합니다."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"JSON 파일 로드 중 오류 발생: {e}")
        return []


def create_character_node(
    db_manager: DBInterface, character_data: Dict[str, Any]
) -> None:
    """캐릭터 노드를 생성합니다."""
    query = """
    CREATE (c:Character)
    SET c += $properties
    """
    db_manager.query(query=query, params={"properties": character_data})


def flatten_properties(data: Dict[str, Any]) -> Dict[str, Any]:
    """중첩된 맵 구조를 평탄화하거나 JSON 문자열로 변환합니다."""
    flattened = {}
    for key, value in data.items():
        if isinstance(value, dict):
            # 중첩된 딕셔너리는 JSON 문자열로 변환
            flattened[key] = json.dumps(value)
        elif isinstance(value, list):
            # 리스트 내의 딕셔너리도 JSON 문자열로 변환
            if any(isinstance(item, dict) for item in value):
                flattened[key] = json.dumps(value)
            else:
                flattened[key] = value
        else:
            flattened[key] = value
    return flattened


def create_map_node(db_manager: DBInterface, map_data: Dict[str, Any]) -> None:
    """맵 노드를 생성합니다."""
    query = """
    CREATE (m:Map)
    SET m += $properties
    """
    # 속성을 평탄화하여 저장
    flattened_properties = flatten_properties(map_data)
    db_manager.query(query=query, params={"properties": flattened_properties})


def create_scene_node(db_manager: DBInterface, scene_data: Dict[str, Any]) -> None:
    """씬 노드를 생성합니다."""
    query = """
    CREATE (s:Scene)
    SET s += $properties
    """
    # scene_beats를 제외한 나머지 속성을 평탄화
    properties = {k: v for k, v in scene_data.items() if k != "scene_beats"}
    flattened_properties = flatten_properties(properties)
    db_manager.query(query=query, params={"properties": flattened_properties})


def create_scene_beat_node(
    db_manager: DBInterface, scene_beat_data: Dict[str, Any]
) -> None:
    """씬 비트 노드를 생성합니다."""
    query = """
    CREATE (sb:SceneBeat)
    SET sb += $properties
    """
    properties = {k: v for k, v in scene_beat_data.items() if k != "next_scene_beats"}
    flattened_properties = flatten_properties(properties)
    db_manager.query(query=query, params={"properties": flattened_properties})


def create_relationship(
    db_manager, source_id, target_id, relationship_type, properties=None
):
    """
    두 노드 간의 관계를 생성합니다.

    Args:
        db_manager: 데이터베이스 관리자 인스턴스
        source_id: 소스 노드 ID
        target_id: 타겟 노드 ID
        relationship_type: 관계 유형
        properties: 관계에 추가할 속성 (선택적)
    """
    query = (
        f"MATCH (a), (b) "
        f"WHERE a.id = $source_id AND b.id = $target_id "
        f"CREATE (a)-[r:{relationship_type}]->(b)"
    )

    params = {"source_id": source_id, "target_id": target_id}

    # 속성이 제공된 경우, 관계에 속성 설정
    if properties:
        props_str = ", ".join(f"r.{key} = ${key}" for key in properties.keys())
        if props_str:
            query = (
                f"MATCH (a), (b) "
                f"WHERE a.id = $source_id AND b.id = $target_id "
                f"CREATE (a)-[r:{relationship_type}]->(b) "
                f"SET {props_str}"
            )
            # 매개변수에 속성 추가
            params.update({key: value for key, value in properties.items()})

    db_manager.query(query=query, params=params)


def create_location_node(
    db_manager: DBInterface, map_id: str, location_data: dict
) -> None:
    """위치 노드를 생성하고 맵과의 관계를 설정합니다.

    Args:
        db_manager: 데이터베이스 매니저 인터페이스
        map_id: 맵 ID
        location_data: 위치 데이터 딕셔너리
    """
    # 위치 노드 생성
    create_query = """
    CREATE (l:Location {id: $id, x: $x, y: $y, type: $type, destination: $destination})
    """
    db_manager.query(
        query=create_query,
        params={
            "id": location_data["id"],
            "x": location_data["x"],
            "y": location_data["y"],
            "type": location_data["type"],
            "destination": location_data["destination"],
        },
    )

    # 맵과 위치 노드 간의 관계 생성
    relate_query = """
    MATCH (m:Map {id: $map_id})
    MATCH (l:Location {id: $location_id})
    CREATE (m)-[:HAS_LOCATION]->(l)
    """
    db_manager.query(
        query=relate_query,
        params={"map_id": map_id, "location_id": location_data["id"]},
    )


def extract_entities_and_relationships(
    user_input: str, schema: str = ""
) -> Dict[str, Any]:
    """
    Extract entity and relationship from user_input :

    Args:
        user_input: text what user write
        schema: information of user database (optional)

    Returns:
        The dictionary what contained entities and relationships.
        example : {"nodes": [...], "relationships": [...]}
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


def _upsert_node(neo4j_graph, label: str, node_properties: Dict[str, Any]) -> None:
    """노드를 생성하거나 업데이트합니다.

    Args:
        neo4j_graph: Neo4j 그래프 객체
        label: 노드 레이블
        node_properties: 노드 속성
    """
    query = f"""
    MERGE (n:{label} {{id: $properties.id}})
    SET n += $properties
    """
    neo4j_graph.query(query=query, params={"properties": node_properties})


def _upsert_relationship(
    neo4j_graph,
    from_label: str,
    from_id: str,
    rel_type: str,
    to_label: str,
    to_id: str,
    rel_properties: Dict[str, Any] = None,
) -> None:
    """두 노드 간 관계를 생성하거나 업데이트합니다.

    Args:
        neo4j_graph: Neo4j 그래프 객체
        from_label: 시작 노드 레이블
        from_id: 시작 노드 ID
        rel_type: 관계 유형
        to_label: 끝 노드 레이블
        to_id: 끝 노드 ID
        rel_properties: 관계 속성 (기본값: None)
    """
    if rel_properties is None:
        rel_properties = {}

    query = f"""
    MATCH (a:{from_label} {{id: $from_id}}), (b:{to_label} {{id: $to_id}})
    MERGE (a)-[r:{rel_type}]->(b)
    SET r += $rel_properties
    """
    neo4j_graph.query(
        query=query,
        params={"from_id": from_id, "to_id": to_id, "rel_properties": rel_properties},
    )


def get_map_data(db_manager: DBInterface, map_id: str) -> Dict[str, Any]:
    query = """
    MATCH (m:Map {id: $map_id})
    RETURN m
    """
    result = db_manager.query(query=query, params={"map_id": map_id})
    if result:
        node_data = result[0]["m"]
        # JSON 문자열로 저장된 속성을 다시 파싱
        parsed_data = {}
        for key, value in node_data.items():
            if isinstance(value, str) and value.startswith("{"):
                try:
                    parsed_data[key] = json.loads(value)
                except json.JSONDecodeError:
                    parsed_data[key] = value
            else:
                parsed_data[key] = value
        return parsed_data
    return None
