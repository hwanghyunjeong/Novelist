# app.py
import streamlit as st
import uuid
from state_graph import create_state_graph
from story_chain import create_story_chain, create_map_analyst
from db import DBManager
from db_utils import extract_entities_and_relationships, update_graph_from_er
from states import PlayerState 
import json
from neo4j import GraphDatabase
from typing import List, Dict
import os
from dotenv import load_dotenv
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

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY is not set in .env file")


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


def get_next_scene_beat(
    db_client: GraphDatabase, current_scene_beat_id: str, choice: str = ""
) -> str:
    """
    현재 씬 비트 ID에서 다음 씬 비트 ID를 가져옵니다.
    현재 씬에 여러 개의 다음 ID가 있는 경우, 선택에 따라 반환합니다.
    """
    try:
        with db_client.session() as session:
            if choice == "":
                result = session.run(
                    """
                    MATCH (sb:SceneBeat {id: $current_scene_beat_id})-[:NEXT]->(next_sb)
                    RETURN next_sb.id AS next_scene_beat_id
                    """,
                    current_scene_beat_id=current_scene_beat_id,
                )
            else:
                result = session.run(
                    """
                    MATCH (sb:SceneBeat {id: $current_scene_beat_id})-[:NEXT]->(next_sb)
                    WHERE $choice in next_sb.id
                    RETURN next_sb.id AS next_scene_beat_id
                    """,
                    current_scene_beat_id=current_scene_beat_id,
                    choice=choice,
                )
            next_scene_beats = [record["next_scene_beat_id"] for record in result]

            if not next_scene_beats:
                raise ValueError(
                    f"No next scene beat found for {current_scene_beat_id}"
                )

            return next_scene_beats[0]
    except Exception as e:
        print(f"Error during scene transition: {e}")
        return None


def get_scene_map_id(db_client: GraphDatabase, scene_id: str) -> str:
    """주어진 씬 ID와 연결된 맵 ID를 가져옵니다."""
    try:
        with db_client.session() as session:
            result = session.run(
                """
                MATCH (s:Scene {id: $scene_id})-[:TAKES_PLACE_IN]->(m:Map)
                RETURN m.id AS map_id
                """,
                scene_id=scene_id,
            )
            map_ids = [record["map_id"] for record in result]
            if not map_ids:
                raise ValueError(f"No map found for scene {scene_id}")
            return map_ids[0]
    except Exception as e:
        print(f"Error during getting map_id: {e}")
        return None


def is_choice_scene(db_client: GraphDatabase, scene_beat_id: str) -> bool:
    """씬 비트가 선택 씬인지 확인합니다."""
    try:
        with db_client.session() as session:
            result = session.run(
                """
                MATCH (sb:SceneBeat {id:$scene_beat_id})
                RETURN sb.next_scene_beat_id as next_ids
                """,
                scene_beat_id=scene_beat_id,
            )
            next_ids = [record["next_ids"] for record in result]
            if len(next_ids[0]) > 1:
                return True
            else:
                return False
    except Exception as e:
        print(f"Error during check choice scene: {e}")
        return False


def get_available_actions(db_client: GraphDatabase, scene_id: str) -> List[str]:
    """현재 씬에서 가능한 행동들을 가져옵니다."""
    try:
        with db_client.session() as session:
            result = session.run(
                """
                MATCH (s:Scene {id: $scene_id})
                RETURN s.available_actions AS available_actions
                """,
                scene_id=scene_id,
            )
            available_actions = [record["available_actions"] for record in result]
            return available_actions[0]
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


def update_state(data):
    # LangGraph 에 필요한 state update
    return data


def ere_extraction_node(data):
    """사용자 입력으로부터 엔티티와 관계를 추출하고 그래프를 업데이트합니다."""
    user_input = data.get("user_input")
    if user_input:
        db_client = data.get("db_client")
        try:
            extracted_data = extract_entities_and_relationships(user_input)
            update_graph_from_er(db_client, extracted_data)
            data["extracted_data"] = extracted_data
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
            return data

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
    """사용자 입력이 유효한 행동인지 확인합니다."""
    user_input = data.get("user_input")
    current_scene_id = data.get("scene")
    db_client = data.get("db_client")
    available_actions = get_available_actions(db_client, current_scene_id)
    data["available_actions"] = available_actions
    is_valid_input = check_action_in_available_actions(user_input, available_actions)
    if is_valid_input:
        return "continue"
    else:
        return "invalid_input"


# Create Langgraph
story_chain = create_story_chain()
map_analyst = create_map_analyst()
node_map = {
    "check_action": check_valid_action, # 수정
    "scene_transition": scene_transition_node, # 수정
    "ere_extraction": ere_extraction_node, # 수정
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
    check_valid_action,
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


def main():
    # 페이지 제목과 레이아웃 설정
    st.set_page_config(page_title="Interactive Novel", layout="wide")

    # 세션 및 초기 상태 로드
    if "session_id" not in st.session_state:
        st.session_state["session_id"] = str(uuid.uuid4())
    if "game_state" not in st.session_state:
        game_state = load_initial_state()
        game_state["session_id"] = st.session_state["session_id"]  # session_id를 상태에 포함
        st.session_state["game_state"] = game_state
    # 편의상 지역 변수에 게임 상태 저장
    game_state = st.session_state["game_state"]

    st.title("Interactive Novel")
    st.subheader("현재까지의 이야기:")
    story_so_far = game_state.get("generation", "")
    if story_so_far:
        st.write(story_so_far)
    else:
        st.write("*(이야기가 아직 시작되지 않았습니다.)*")

    # 현재 씬의 사용 가능 행동 불러오기
    current_scene_id = game_state["scene"]
    # DB 연결 확인 및 설정
    if "db_manager" not in st.session_state:
        try:
            st.session_state["db_manager"] = DBManager(
                uri="bolt://localhost:7687", user="neo4j", password="11111111"
            )
            game_state["db_client"] = st.session_state["db_manager"].driver
        except Exception as e:
            st.error("데이터베이스 연결에 실패했습니다.")
    # DB 드라이버 객체 가져오기
    db_client = game_state.get("db_client")
    available_actions = get_available_actions(db_client, current_scene_id)
    st.write(
        "사용 가능한 행동: " + ", ".join(available_actions)
        if available_actions
        else "사용 가능한 행동이 없습니다."
    )

    # 입력 폼 생성
    with st.form("action_form", clear_on_submit=True):
        user_text = st.text_input("행동 또는 대사를 입력하세요:")
        submitted = st.form_submit_button("제출")

    if submitted:
        user_input = user_text.strip()
        if user_input == "":
            st.warning("행동을 입력해주세요.")  # 빈 입력에 대한 처리
        elif not check_action_in_available_actions(user_input, available_actions):
            st.warning(
                f"유효한 행동을 입력하세요. 가능한 행동: {', '.join(available_actions)}"
            )
        else:
            # 유효한 입력일 경우에만 게임 상태 업데이트 및 LangGraph 호출
            game_state["user_input"] = user_input
            game_state["history"].append(user_input)
            old_scene_beat = game_state["scene_beat"]
            try:
                new_state = app.invoke(game_state)
            except Exception as e:
                st.error(f"게임 진행 중 오류가 발생했습니다: {e}")
                st.stop()
            # 필요한 상태 키 보존 (db_client 등)
            if "db_client" not in new_state:
                new_state["db_client"] = game_state.get("db_client")
            if "session_id" not in new_state:
                new_state["session_id"] = game_state.get("session_id")
            st.session_state["game_state"] = new_state  # 세션 상태 업데이트
            # 추출된 정보 및 생성된 이야기 출력
            st.write("추출된 정보:")
            st.write(new_state.get("extracted_data", {}))
            st.write("생성된 이야기:")
            st.write(new_state.get("generation", ""))
            # 다음 씬 진행 여부 확인
            if new_state.get("scene_beat") == old_scene_beat:
                st.info("더 이상 진행할 이야기가 없습니다. 게임이 종료되었습니다.")
                # (필요 시 추가 종료 처리)
            # 게임 상태를 DB에 저장
            st.session_state["db_manager"].save_state(new_state)


if __name__ == "__main__":
    main()

