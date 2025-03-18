# app.py
import streamlit as st
import config
import uuid
from state_graph import create_state_graph
from story_chain import create_story_chain, create_map_analyst
from db_interface import DBInterface
from db_factory import get_db_manager
from db_state_injector import DBStateInjector
from db_utils import extract_entities_and_relationships, update_graph_from_er
from states import PlayerState, player_state_to_dict
import json
from neo4j import GraphDatabase
from typing import List, Dict, Any, Optional
import os
from langgraph.graph import StateGraph, END
from node import (
    CreatePlayerAndCharacterNodes,
    InitializeNode,
    AnalysisDirectionNode,
    MovePlayerNode,
    AnalyseMapNode,
    MakeStoryNode,
    RouteMovingNode,
)
from abc import ABC, abstractmethod
from langchain_neo4j import Neo4jGraph
from db_interface import DBInterface
from db_manager import LangchainNeo4jDBManager
from db_state_injector import DBStateInjector
from db_factory import get_db_manager
from action_matcher import ActionMatcher
from map_agent import MapAgent

OPENAI_API_KEY = config.OPENAI_API_KEY
GOOGLE_API_KEY = config.GOOGLE_API_KEY


def load_initial_state() -> PlayerState:
    """
    Load the initial game state.
    If the JSON file is missing or invalid, return a default initial state.
    """
    # 현재 스크립트의 디렉토리를 가져옵니다.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # 파일의 상대 경로를 구성합니다.
    state_file_path = os.path.join(
        script_dir, "data", "state", "sample_game_state.json"
    )

    default_state = {
        "player": {
            "id": "character:Player",
            "name": "Player",
            "sex": "unknown",
            "position": {"map": "map:Pangyo_B2_Concourse", "x": 1, "y": 1},
            "direction": "north",
            "field_of_view": 3,
            "inventory": [],
            "stamina": 100,
            "status": "normal",
        },
        "map": "map:Pangyo_B2_Concourse",
        "scene": "scene:00_Pangyo_Station",
        "scene_beat": "scene_beat:00_Pangyo_Station_1",
        "history": [],
        "user_input": "",
        "map_context": "",
        "generation": "",
        "characters": [],
        "extracted_data": {},
    }

    try:
        with open(state_file_path, "r", encoding="utf-8") as f:
            initial_state_data = json.load(f)
        return PlayerState(initial_state_data)
    except (FileNotFoundError, json.JSONDecodeError):
        print(
            "Warning: Using default game state as the JSON file is missing or invalid."
        )
        return PlayerState(initial_state_data)


game_state = load_initial_state()  # 초기 게임 상태 로드


def get_next_scene_beat(db_client, current_scene_beat_id: str, choice: str = "") -> str:
    """현재 씬 비트 ID에서 다음 씬 비트 ID를 가져옵니다."""
    try:
        if choice == "":
            query = """
            MATCH (sb:SceneBeat {id: $current_scene_beat_id})-[:NEXT]->(next_sb)
            RETURN next_sb.id AS next_scene_beat_id
            """
        else:
            query = """
            MATCH (sb:SceneBeat {id: $current_scene_beat_id})-[:NEXT]->(next_sb)
            WHERE $choice in next_sb.id
            RETURN next_sb.id AS next_scene_beat_id
            """

        result = db_client.query(
            query, {"current_scene_beat_id": current_scene_beat_id, "choice": choice}
        )

        if not result:
            raise ValueError(f"No next scene beat found for {current_scene_beat_id}")

        return result[0]["next_scene_beat_id"]
    except Exception as e:
        print(f"Error during scene transition: {e}")
        return None


def get_scene_map_id(db_client, scene_id: str) -> str:
    """주어진 씬 ID와 연결된 맵 ID를 가져옵니다."""
    try:
        query = """
        MATCH (s:Scene {id: $scene_id})-[:TAKES_PLACE_IN]->(m:Map)
        RETURN m.id AS map_id
        """
        result = db_client.query(query, {"scene_id": scene_id})

        if not result:
            raise ValueError(f"No map found for scene {scene_id}")

        return result[0]["map_id"]
    except Exception as e:
        print(f"Error during getting map_id: {e}")
        return None


def is_choice_scene(db_client, scene_beat_id: str) -> bool:
    """씬 비트가 선택 씬인지 확인합니다."""
    try:
        query = """
        MATCH (sb:SceneBeat {id:$scene_beat_id})
        RETURN sb.next_scene_beat_id as next_ids
        """
        result = db_client.query(query, {"scene_beat_id": scene_beat_id})

        if not result:
            return False

        next_ids = result[0]["next_ids"]
        return len(next_ids) > 1
    except Exception as e:
        print(f"Error during check choice scene: {e}")
        return False


def get_available_actions(db_client, scene_id: str) -> List[str]:
    """현재 씬에서 가능한 행동들을 가져옵니다."""
    try:
        query = """
        MATCH (s:Scene {id: $scene_id})
        RETURN s.available_actions AS available_actions
        """
        result = db_client.query(query, {"scene_id": scene_id})

        if not result:
            return []

        return result[0]["available_actions"]
    except Exception as e:
        print(f"Error during get available action : {e}")
        return []


def check_action_in_available_actions(
    user_input: str, available_actions: List[str]
) -> bool:
    """사용자 입력이 가능한 행동 목록에 있는지 확인합니다."""
    if any(action in user_input.lower() for action in available_actions):
        return True
    else:
        return False


def choice_make(user_input: str, scene_beat_id: str) -> str:
    """사용자 입력에 따라 선택지를 만듭니다."""
    if scene_beat_id == "scene_beat:00_Pangyo_Station_3":
        if "help" in user_input.lower():
            return "scene_beat:00_Pangyo_Station_4"
        elif "pass" in user_input.lower():
            return "scene:01_Underground_Platform_GG"
    return ""


# 추출된 데이터를 미리 extracted_data에 저장한 뒤에 업데이트 하도록 변경 (자료 손실 예방)
def ere_extraction_node(data):
    """사용자 입력으로부터 엔티티와 관계를 추출하고 그래프를 업데이트합니다."""
    user_input = data.get("user_input")
    if user_input:
        db_client = data.get("db_client")
        try:
            extracted_data = extract_entities_and_relationships(user_input)
            data["extracted_data"] = extracted_data
            update_graph_from_er(db_client, extracted_data)
        except Exception as e:
            print(f"Error during ere_extraction_node : {e}")
    return data


def scene_transition_node(data):
    """사용자 입력과 게임 상태에 따라 다음 씬으로 전환합니다."""
    user_input = data.get("user_input")
    current_scene_id = data.get("scene")
    current_scene_beat_id = data.get("scene_beat")
    db_client = data.get("db_client")
    # choice making
    choice = choice_make(user_input, current_scene_beat_id)
    try:
        next_scene_beat = get_next_scene_beat(db_client, current_scene_beat_id, choice)

        if not next_scene_beat:
            print(f"No valid next scene beat. scene_beat: {next_scene_beat}")
            return data.update({"scene_beat": None})

        data["scene_beat"] = next_scene_beat

        # Update scene
        if next_scene_beat.startswith("scene:"):
            data["scene"] = next_scene_beat

            # Update map
            next_scene_id = next_scene_beat
            map_id = get_scene_map_id(db_client, next_scene_id)
            if not map_id:
                print(f"No valid map_id. scene: {next_scene_id}")
                return data

            data["map"] = map_id
    except ValueError as e:
        print(f"Error: {e}")
    return data


def check_valid_action(data):
    current_scene_id = data.get("scene")
    db_client = data.get("db_client")
    available_actions = get_available_actions(db_client, current_scene_id)
    data["available_actions"] = available_actions
    # 입력이 유효했는지 검증하는 action result (임시)
    data["action_result"] = (
        "continue"
        if check_action_in_available_actions(
            data.get("user_input", ""), available_actions
        )
        else "invalid_input"
    )
    return data


def get_player_data(db_client) -> Dict:
    """Neo4j에서 플레이어 데이터를 가져옵니다."""
    try:
        query = """
        MATCH (p:Player {id: "character:Player"})
        RETURN p.name AS name, p.sex AS sex
        """
        result = db_client.query(query)

        if not result:
            return None

        return {"name": result[0]["name"], "sex": result[0]["sex"]}
    except Exception as e:
        st.error(f"플레이어 데이터를 가져오는 중 오류 발생: {e}")
        return None


def create_player_in_db(db_client, player_data: Dict):
    """Neo4j에 플레이어 데이터를 생성합니다."""
    try:
        query = """
        MERGE (p:Player {id: "character:Player"})
        ON CREATE SET p.name = $name, p.sex = $sex
        """
        db_client.query(query, {"name": player_data["name"], "sex": player_data["sex"]})
        st.success("플레이어 정보가 Neo4j에 저장되었습니다.")
    except Exception as e:
        st.error(f"플레이어 데이터 생성 중 오류 발생: {e}")


# Create Langgraph
story_chain = create_story_chain()
map_analyst = create_map_analyst()
node_map = {
    "check_action": check_valid_action,  # 수정
    "scene_transition": scene_transition_node,  # 수정
    "ere_extraction": ere_extraction_node,  # 수정
    "story_generation": MakeStoryNode(story_chain).execute,
    "initialize": InitializeNode().execute,
    "create_player_and_character": CreatePlayerAndCharacterNodes().execute,
    "analysis_direction": AnalysisDirectionNode().execute,
    "move_player": MovePlayerNode().execute,
    "map_analyst": AnalyseMapNode(map_analyst).execute,
}

workflow = StateGraph(PlayerState)
for name, n in node_map.items():
    workflow.add_node(name, n)

workflow.set_entry_point("initialize")
workflow.add_edge("initialize", "create_player_and_character")
workflow.add_edge("create_player_and_character", "check_action")
workflow.add_conditional_edges(
    "check_action",
    # check_valid_action,
    lambda state: state.get("action_result"),
    {
        "continue": "scene_transition",
        "invalid_input": END,
    },
)

workflow.add_edge("scene_transition", "ere_extraction")
workflow.add_edge("ere_extraction", "analysis_direction")
workflow.add_conditional_edges(
    "analysis_direction",
    RouteMovingNode().execute,
    {"move_player": "move_player", "map_analyst": "map_analyst"},
)
workflow.add_edge("move_player", "map_analyst")
workflow.add_edge("map_analyst", "story_generation")

workflow.add_edge("story_generation", END)

app = workflow.compile()


def initialize_game_state():
    """게임 상태를 초기화합니다."""
    if "db_manager" not in st.session_state:
        st.session_state.db_manager = get_db_manager()

    if "state" not in st.session_state:
        injector = DBStateInjector(st.session_state.db_manager)
        st.session_state.state = injector.inject({})
        st.session_state.action_matcher = ActionMatcher()


def display_game_state():
    """현재 게임 상태를 표시합니다."""
    st.title("Novelist : interactive novel")

    if "context" in st.session_state.state:
        st.markdown("### 현재까지의 이야기:")
        st.write(st.session_state.state["context"])

    if "available_actions" in st.session_state.state:
        st.markdown("### 가능한 행동:")
        for action in st.session_state.state["available_actions"]:
            st.write(f"- {action}")


def update_game_state(action: str) -> None:
    """매칭된 액션에 따라 게임 상태를 업데이트합니다."""
    try:
        current_scene = st.session_state.state.get("current_scene", {})
        current_beat = st.session_state.state.get("current_beat")

        # MapAgent 초기화 (필요한 경우)
        if "map_agent" not in st.session_state:
            st.session_state.map_agent = MapAgent(st.session_state.db_manager)

        # 맵 데이터 업데이트
        if "map" in current_scene:
            map_data = st.session_state.map_agent.load_map(current_scene["map"])
            if map_data:
                st.session_state.state["current_map"] = map_data

        # 비트 업데이트 로직
        if current_beat:
            next_beat = get_next_beat(current_beat, action)
            if next_beat:
                st.session_state.state["current_beat"] = next_beat
                st.session_state.state["context"] = next_beat.get("context", "")
                st.session_state.state["available_actions"] = next_beat.get(
                    "available_actions", []
                )
        else:
            scene_beats = current_scene.get("scene_beats", [])
            if scene_beats:
                first_beat = scene_beats[0]
                st.session_state.state["current_beat"] = first_beat
                st.session_state.state["context"] = first_beat.get("context", "")
                st.session_state.state["available_actions"] = first_beat.get(
                    "available_actions", []
                )

        save_game_state()

    except Exception as e:
        st.error(f"게임 상태 업데이트 중 오류 발생: {str(e)}")


def get_next_beat(
    current_beat: Dict[str, Any], action: str
) -> Optional[Dict[str, Any]]:
    """현재 비트에서 선택된 액션에 따른 다음 비트를 반환합니다."""
    try:
        # 다음 비트 ID 목록 가져오기
        next_beat_ids = current_beat.get("next_scene_beats", [])

        if not next_beat_ids:
            return None

        # Neo4j에서 다음 비트 정보 조회
        query = """
        MATCH (sb:SceneBeat)
        WHERE sb.id IN $next_beat_ids
        RETURN sb
        """

        results = st.session_state.db_manager.query(
            query, {"next_beat_ids": next_beat_ids}
        )

        if results:
            # 첫 번째 다음 비트 반환 (추후 조건부 분기 로직 추가 가능)
            next_beat_data = results[0]["sb"]
            return parse_node_data(next_beat_data)

        return None

    except Exception as e:
        st.error(f"다음 비트 조회 중 오류 발생: {str(e)}")
        return None


def parse_node_data(node_data: Dict[str, Any]) -> Dict[str, Any]:
    """Neo4j 노드 데이터를 파싱합니다."""
    import json

    parsed_data = {}
    for key, value in node_data.items():
        if isinstance(value, str) and (value.startswith("{") or value.startswith("[")):
            try:
                parsed_data[key] = json.loads(value)
            except json.JSONDecodeError:
                parsed_data[key] = value
        else:
            parsed_data[key] = value
    return parsed_data


def save_game_state() -> None:
    """현재 게임 상태를 저장합니다."""
    try:
        # 저장할 상태 데이터 준비
        state_data = {
            "current_scene_id": st.session_state.state.get("current_scene", {}).get(
                "id"
            ),
            "current_beat_id": st.session_state.state.get("current_beat", {}).get("id"),
            "context": st.session_state.state.get("context", ""),
            "player_name": st.session_state.state.get("player", {}).get("name", ""),
            "player_gender": st.session_state.state.get("player", {}).get("gender", ""),
            "current_map_id": st.session_state.state.get("current_map", {}).get(
                "id", ""
            ),
        }

        # 모든 값이 원시 타입인지 확인
        for key, value in state_data.items():
            if value is None:
                state_data[key] = ""  # None을 빈 문자열로 변환

        query = """
        MERGE (gs:GameState {player_id: $player_id})
        SET gs += $state_data
        """

        st.session_state.db_manager.query(
            query,
            {
                "player_id": st.session_state.state.get("player", {}).get(
                    "id", "default"
                ),
                "state_data": state_data,
            },
        )

    except Exception as e:
        st.error(f"게임 상태 저장 중 오류 발생: {str(e)}")


def handle_user_input():
    """사용자 입력을 처리합니다."""
    if "previous_input" not in st.session_state:
        st.session_state.previous_input = ""

    user_input = st.text_input("무엇을 하시겠습니까?")

    if user_input and user_input != st.session_state.previous_input:
        st.session_state.previous_input = user_input

        available_actions = st.session_state.state.get("available_actions", [])
        matched_action = st.session_state.action_matcher.find_best_action(
            user_input, available_actions
        )

        if matched_action:
            st.session_state.matched_action = matched_action
            update_game_state(matched_action)
            st.success(f"선택한 행동: {matched_action}")
        else:
            # TypedDict는 딕셔너리로 직접 처리
            current_state = st.session_state.state.copy()
            current_state["action_result"] = "invalid_input"
            current_state["user_input"] = user_input

            # workflow를 통한 처리
            result = app(current_state)  # TypedDict는 딕셔너리를 직접 전달

            if isinstance(result, dict):  # TypedDict도 dict의 일종
                st.markdown("---")
                st.markdown(result.get("generation", ""))
                st.markdown("---")
                st.session_state.state = result
            else:
                st.error("상태 업데이트 중 오류가 발생했습니다.")


def main():
    initialize_game_state()
    display_game_state()
    handle_user_input()


if __name__ == "__main__":
    main()
