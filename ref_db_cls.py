from typing import Annotated, Dict, List, TypedDict, Literal, Union
from typing_extensions import TypedDict

# sample scene schema를 기반으로 추출
"""
최상위 스키마는 RetriveState
여기서 정의된 data의 순서에 따른 것이 Scene, SceneBeat
"""


class SceneBeatStoryScript(TypedDict):
    """
    SceneBeat 노드에 포함된 story_script의 구조 정의
    스크립트 유형, 배경 장소, 등장인물, 행동 묘사, 감정 묘사, 내용 등
    """

    type: Annotated[str, "스크립트의 유형 (예: narrative)"]
    location: Annotated[str, "스크립트의 배경 장소 설명"]
    characters: Annotated[List[str], "스크립트에 등장하는 캐릭터 ID 목록"]
    act: Annotated[List[str], "캐릭터들의 행동 묘사 목록"]
    emotion: Annotated[List[str], "스크립트의 감정 묘사 목록"]
    content: Annotated[List[str], "스크립트의 내용 목록"]


class SceneBeatProperties(TypedDict):
    """
    SceneBeat 노드가 가지는 속성들을 정의
    SceneBeat가 속한 Scene의 ID, 순서, 단계 설명, 줄거리 설명, 모티프 설명, 인과 관계 설명, 스크립트, 다음 SceneBeat ID 등을 포함
    """

    scene_id: Annotated[str, "SceneBeat가 속한 Scene의 ID"]
    beat_index: Annotated[str, "SceneBeat의 순서"]
    stage: Annotated[str, "SceneBeat의 단계 설명"]
    storylines: Annotated[List[str], "SceneBeat의 줄거리 설명 목록"]
    unit_motif: Annotated[str, "SceneBeat의 모티프 설명"]
    causality: Annotated[List[str], "SceneBeat의 인과 관계 설명 목록"]
    story_script: Annotated[SceneBeatStoryScript, "스크립트"]
    next_scene_beat_id: Annotated[
        Union[str, List[str]], "다음 SceneBeat ID 또는 Scene ID 목록"
    ]


class SceneBeat(TypedDict):
    """
    SceneBeat 노드를 정의
    Scene의 하위 단계를 나타내며, 해당 SceneBeat의 ID, 레이블, 속성들을 포함
    """

    id: Annotated[str, "scene_beat:{id}"]
    label: Annotated[Literal["SceneBeat"], "SceneBeat"]
    properties: SceneBeatProperties


class SceneProperties(TypedDict):
    """
    Scene 노드가 가지는 속성들을 정의
    각 씬의 위치, 유형, 장르, 테마, 개념, 모티프, 주요 등장인물, 갈등, 등장인물 목록, 초기 설정, 가능한 행동 등을 포함
    """

    map_id: Annotated[str, "Scene이 발생하는 맵의 ID"]
    scene_type: Annotated[str, "Scene의 유형 (예: Prologue, Turning Point)"]
    genre: Annotated[List[str], "Scene의 장르 목록"]
    theme: Annotated[List[str], "Scene의 테마 목록"]
    concept: Annotated[str, "Scene의 핵심 개념"]
    motif: Annotated[List[str], "Scene의 모티프 목록"]
    main_character: Annotated[str, "Scene의 주요 등장인물 ID"]
    conflict: Annotated[str, "Scene의 갈등 설명"]
    characters: Annotated[List[str], "Scene에 등장하는 캐릭터 ID 목록"]
    initial_setup: Annotated[List[str], "Scene의 초기 설정 설명 목록"]
    available_actions: Annotated[List[str], "Scene에서 가능한 행동 목록"]


class Scene(TypedDict):
    """
    Scene 노드를 정의
    게임의 한 장면을 나타내며, 해당 장면의 ID, 레이블, 속성들을 포함
    """

    id: Annotated[str, "scene:{id}"]
    label: Annotated[Literal["Scene"], "Scene"]
    properties: SceneProperties


class RetriveState(TypedDict):
    """
    데이터 스키마를 정의하는 state
    description : 해당 Scene 또는 SceneBeat의 정의
    data : 해당 Scene 또는 SceneBeat의 데이터 목록을 포함
    """

    description: Annotated[str, "해당 Scene의 정의"]
    data: Annotated[List[Union[Scene, SceneBeat]], "해당 Scene에 해당하는 데이터 목록"]
