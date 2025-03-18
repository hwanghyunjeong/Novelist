from typing import Annotated, Dict, List, TypedDict, Callable, Union
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from neo4j import GraphDatabase
from abc import ABC, abstractmethod
from ref_db_cls import Scene, SceneBeat  # Player state RAG용


# https://wikidocs.net/265768 참조할 것 (서브스키마로 서로 다른 스키마 구조를 가질때)
class GameState(TypedDict):
    """
    게임 상태를 보관하는 state
    """

    player: Annotated[dict, "Attributes and methods of the character the user plays"]
    map: Annotated[dict, "Information about the map (Location, Character, Scene)"]
    init: Annotated[bool, "story initialization"]
    user_input: Annotated[str, "User's input and question"]
    history: Annotated[list, add_messages]
    generation: Annotated[str, "Generated story by LLM"]
    map_context: Annotated[str, "Analysis of the map by LLM"]


class PlayerState(TypedDict):
    """
    플레이어의 상태 및 이야기를 저장하는 TypedDict (speaker)
    """

    player: Annotated[Dict, "사용자가 플레이하는 캐릭터의 속성 및 메소드"]
    map: Annotated[str, "LLM을 거쳐서 해독된 맵의 정보"]
    scene: Annotated[str, "해당 장면을 설명하는 시퀀스, 순차적인 순서를 가짐."]
    scene_beat: Annotated[str, "Scene의 진행을 설명하는 단위, 순차적인 순서를 가짐"]
    history: Annotated[List[str], "이전까지의 대화 및 대화요약"]
    user_input: Annotated[str, "사용자가 입력한 메시지 원문"]
    generation: Annotated[str, "AI로 증강생성시킨 이야기"]
    map_context: Annotated[str, "맵을 분석한 내용"]
    characters: List[Dict]
    extracted_data: Annotated[Dict, "LLM으로 추출된 데이터"]
    session_id: Annotated[str, "st.session_state.id 고유값"]
    available_actions: Annotated[List[str], "사용자가 취할 수 있는 바람직한 행동들"]


def initialize_player_state() -> PlayerState:
    """초기 PlayerState를 생성합니다."""
    return {
        "player": {},
        "map": "",
        "scene": "",
        "scene_beat": "",
        "history": [],
        "user_input": "",
        "generation": "",
        "map_context": "",
        "characters": [],
        "extracted_data": {},
        "session_id": "",
        "available_actions": [],
    }


def update_player_state(state: PlayerState, updates: Dict) -> PlayerState:
    """PlayerState를 업데이트합니다. 새로운 상태 객체를 반환합니다."""
    new_state = state.copy()
    new_state.update(updates)
    return new_state


def player_state_to_dict(player_state: PlayerState) -> Dict:
    """PlayerState 객체를 dict로 변환합니다."""
    return dict(player_state)


class BaseNode(ABC):
    @abstractmethod
    def execute(self, state: PlayerState, db_client: GraphDatabase) -> PlayerState:
        """노드의 실행 로직을 정의합니다."""
        pass


# RAG 생성시에만 사용하기 위해 만들어둔 클래스
class GameContext(TypedDict):
    """PlayerState에서 스토리를 증강생성하여 참조하기 위한 결합 클래스"""

    player_state: PlayerState
    scene_data: Union[Scene, SceneBeat, None]  # 현재 씬 또는 씬 비트 데이터


def initialize_game_context(
    player_state: PlayerState, scene_data: Union[Scene, SceneBeat, None] = None
) -> GameContext:
    return {"player_state": player_state, "scene_data": scene_data}


# (디버그용) 예시 노드 !!!반드시 수정할 것!!!
class ExampleNode(BaseNode):
    def execute(self, state: PlayerState, db_client: GraphDatabase) -> PlayerState:
        """
        예시 노드 실행 메서드.
        """
        print("ExampleNode 실행")

        # db_client를 사용하여 데이터베이스와 상호 작용하는 로직을 추가할 수 있습니다.
        # 예시:
        # with db_client.session() as session:
        #   result = session.run("MATCH (n) RETURN n LIMIT 1")
        #   for record in result:
        #       print(record)

        # 상태를 업데이트합니다.
        updated_state = update_player_state(
            state, {"generation": "Example Node executed."}
        )

        return updated_state


class StateManager:
    """
    PlayerState 관리를 위한 클래스.
    """

    def __init__(self, initial_state: PlayerState = None):
        self.state: PlayerState = (
            initial_state if initial_state is not None else initialize_player_state()
        )

    def get_state(self) -> PlayerState:
        """현재 state를 반환합니다."""
        return self.state

    def update_state(self, updates: Dict):
        """state를 업데이트합니다."""
        self.state = update_player_state(self.state, updates)

    def execute_node(self, node: BaseNode, db_client: GraphDatabase) -> PlayerState:
        """노드를 실행하고 상태를 업데이트합니다."""
        self.state = node.execute(self.state, db_client)
        return self.state
