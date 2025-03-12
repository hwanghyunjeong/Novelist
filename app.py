# app.py
import streamlit as st
import config
import uuid
from state_graph import create_state_graph
from story_chain import create_story_chain, create_map_analyst
from db import DBManager, DBStateInjector
from db_utils import extract_entities_and_relationships, update_graph_from_er
from states import PlayerState, player_state_to_dict
import json
from neo4j import GraphDatabase
from typing import List, Dict
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
            # return data # 이전 scene_beat를 반환하던 것을, 변경된 scene_beat가 없다면, 종료하도록 합니다.
            #  if new_state.get("scene_beat") == None: 조건에서 True가 되어 "더 이상 진행할 이야기가 없습니다" 메시지를 출력하고 게임을 정상적으로 종료
            # 무한루프 방지
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


# 유효하지 않은 액션이라도 일단 반응하도록 처리
# 결과가 같다면 어쨌든 넘어갈 수 있게 처리해야함 (임베딩)
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


# def check_valid_action(data):
#     """사용자 입력이 유효한 행동인지 확인합니다."""
#     user_input = data.get("user_input")
#     current_scene_id = data.get("scene")
#     db_client = data.get("db_client")
#     available_actions = get_available_actions(db_client, current_scene_id)
#     data["available_actions"] = available_actions
#     is_valid_input = check_action_in_available_actions(user_input, available_actions)
#     if is_valid_input:
#         return "continue"
#     else:
#         return "invalid_input"


def get_player_data(db_client: GraphDatabase) -> Dict:
    """Neo4j에서 플레이어 데이터를 가져옵니다."""
    try:
        with db_client.session() as session:
            result = session.run(
                """
                MATCH (p:Player {id: "character:Player"})
                RETURN p.name AS name, p.sex AS sex
                """
            )
            record = result.single()
            if record:
                return {"name": record["name"], "sex": record["sex"]}
            else:
                return None
    except Exception as e:
        st.error(f"플레이어 데이터를 가져오는 중 오류 발생: {e}")
        return None


def create_player_in_db(db_client: GraphDatabase, player_data: Dict):
    """Neo4j에 플레이어 데이터를 생성합니다."""
    try:
        with db_client.session() as session:
            session.run(
                """
                MERGE (p:Player {id: "character:Player"})
                ON CREATE SET p.name = $name, p.sex = $sex
                """,
                name=player_data["name"],
                sex=player_data["sex"],
            )
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


def main():
    # 페이지 제목과 레이아웃 설정
    st.set_page_config(page_title="Interactive Novel", layout="wide")
    # 세션 및 초기 상태 로드 (전역 game_state를 session_state에 저장)
    if "game_state" not in st.session_state:
        st.session_state["game_state"] = game_state  # 전역 game_state 사용
    # 로컬 변수 current_state에 할당하여 사용 (전역 변수 재할당을 피함)
    current_state = st.session_state["game_state"]

    @st.cache_resource
    def get_db_manager():
        return DBManager(config.NEO4J_URI, config.NEO4J_USER, config.NEO4J_PASSWORD)

    if "db_manager" not in st.session_state:
        try:
            st.session_state["db_manager"] = get_db_manager()
            print("DB 연결 성공:", st.session_state["db_manager"].driver)
        except Exception as e:
            st.error(f"데이터베이스 연결에 실패했습니다: {e}")
            st.stop()
    # state를 불러온 직후 DBStateInjector를 사용하여 db_client 재주입
    injector = DBStateInjector(st.session_state["db_manager"])
    current_state = injector.inject(current_state)

    if "session_id" not in st.session_state:
        st.session_state["session_id"] = str(uuid.uuid4())
        current_state["session_id"] = st.session_state["session_id"]

    st.title("Interactive Novel")
    st.subheader("현재까지의 이야기:")
    story_so_far = current_state.get("generation", "")

    if story_so_far:
        st.write(story_so_far)
    else:
        st.write("이야기가 아직 시작되지 않았습니다.")

    # db_manager로부터 db_client 주입 (저장하지 않고 필요할 때만 사용)
    db_client = st.session_state["db_manager"].driver
    available_actions = get_available_actions(db_client, current_state["scene"])
    st.write(
        "사용 가능한 행동: " + ", ".join(available_actions)
        if available_actions
        else "사용 가능한 행동이 없습니다."
    )

    # 플레이어 데이터 로드 또는 입력
    if (
        "db_manager" in st.session_state
        and "player_data_loaded" not in st.session_state
    ):
        player_data = get_player_data(db_client)
        if player_data:
            current_state["player"]["name"] = player_data["name"]
            current_state["player"]["sex"] = player_data["sex"]
            st.session_state["player_data_loaded"] = True
        else:
            st.subheader("플레이어 정보를 입력하세요")
            player_name = st.text_input("이름:")
            player_sex = st.radio("성별:", ("Male", "Female"))
            if st.button("등록"):
                if player_name and player_sex:
                    create_player_in_db(
                        db_client, {"name": player_name, "sex": player_sex}
                    )
                    current_state["player"]["name"] = player_name
                    current_state["player"]["sex"] = player_sex
                    st.session_state["player_data_loaded"] = True
                    st.rerun()
                else:
                    st.warning("이름과 성별을 모두 입력해주세요.")

    with st.form("action_form", clear_on_submit=True):
        user_text = st.text_input("행동 또는 대사를 입력하세요:")
        submitted = st.form_submit_button("제출")

    if submitted:
        user_input = user_text.strip()
        if not user_input:
            st.warning("행동을 입력해주세요.")
        elif not check_action_in_available_actions(user_input, available_actions):
            st.warning(
                f"유효한 행동을 입력하세요. 가능한 행동: {', '.join(available_actions)}"
            )
        else:
            current_state["user_input"] = user_input
            current_state["history"].append(user_input)
            old_scene_beat = current_state["scene_beat"]

            try:
                new_state = injector.invoke_workflow(current_state, app)
            except Exception as e:
                st.error(f"게임 진행 중 오류가 발생했습니다: {e}")
                st.stop()
            # 실행 후 db_client는 저장 대상에서 제외 (직렬화 문제 회피를 위함)
            new_state.pop("db_client", None)
            if "session_id" not in new_state:
                new_state["session_id"] = current_state.get("session_id")
            st.session_state["game_state"] = new_state
            st.write("추출된 정보:")
            st.write(new_state.get("extracted_data", {}))
            st.write("생성된 이야기:")
            st.write(new_state.get("generation", ""))
            # scene_transition_node에서 다음 scene_beat를 찾을 수 없는 경우,
            # 이전 scene_beat를 유지하며 계속 진행하는 것으로 여겨져 무한루프였음.
            # old_scene_beat의 값은 이전 scene_beat의 id이기 때문
            if new_state.get("scene_beat") == None:
                st.info("더 이상 진행할 이야기가 없습니다. 게임이 종료되었습니다.")
            elif new_state.get("scene_beat") == old_scene_beat:
                st.info("더 이상 진행할 이야기가 없습니다. 게임이 종료되었습니다.")
            st.session_state["db_manager"].save_state(new_state)


if __name__ == "__main__":
    main()
