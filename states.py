from typing import Annotated, Dict, List
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages

# from story_class import AsciiMap, Character


class GameState(TypedDict):
    """
    게임 상태를 보관

    player: 사용자
    map: 맵 정보
    init: 이야기 시작 여부
    user_input: 사용자 입력
    history: 대화내역
    generation: AI가 만든 이야기.
    """

    player: Annotated[dict, "사용자가 플레이하는 캐릭터의 속성 및 메소드"]
    map: Annotated[dict, "TRPG 맵의 속성 및 메소드"]
    init: Annotated[bool, "이야기의 처음인지 판단"]
    user_input: Annotated[str, "사용자의 답변 또는 질문"]
    history: Annotated[list, add_messages]  # 사용자와 게임 마스터 사이의 메시지
    gnenration: Annotated[str, "AI가 만든 이야기"]
    map_context: Annotated[str, "맵을 분석한 내용"]

class PlayerState:
    def __init__(self, data: Dict = None):
        if data is None:
            data = {}
        self.player: Dict = data.get("player", {})
        self.map: str = data.get("map", "")
        self.scene: str = data.get("scene", "")
        self.scene_beat: str = data.get("scene_beat", "")
        self.history: List[str] = data.get("history", [])
        self.user_input: str = data.get("user_input", "")
        self.generation: str = data.get("generation", "")
        self.map_context: str = data.get("map_context", "")
        self.characters: List[Dict] = data.get("characters", [])
        self.extracted_data: Dict = data.get("extracted_data", {})
        self.db_client = data.get("db_client")
        self.session_id = data.get("session_id")
        self.available_actions: List[str] = data.get('available_actions', [])

    def get(self, key, default=None):
        return getattr(self, key, default)

    def __getitem__(self, key):
        return getattr(self, key)

    def __setitem__(self, key, value):
        setattr(self, key, value)

    def update(self, data: Dict):
        for key, value in data.items():
          setattr(self, key, value)