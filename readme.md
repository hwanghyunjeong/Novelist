# Novelist (실시간 상호작용 스토리텔러)

Novelist는 LangChain과 LangGraph, OpenAI API, Gemini API, 그리고 Neo4j 그래프 데이터베이스를 활용하여 구현된 실시간 상호작용 스토리텔러입니다. 

이 프로젝트는 사용자가 참여하는 유사 TRPG(Tabletop Role-Playing Game) 경험을 제공하는 것을 목표로 합니다. 

사용자는 텍스트 기반의 입력을 통해 게임에 참여하고, AI는 실시간으로 스토리를 생성하며 게임을 진행하지만, 화면에 나타나는 모든 이야기는 소설의 형태를 가집니다.

## 주요 기능

- 동적 스토리 생성: OpenAI API와 Gemini API를 활용하여 사용자의 입력에 따라 실시간으로 변화하는 스토리를 생성합니다.
- 게임 상태 관리: LangGraph를 사용하여 게임의 진행 상태를 효과적으로 관리합니다.
- 그래프 데이터베이스: Neo4j를 사용하여 게임의 요소, 관계, 상태를 관리합니다.
- 사용자 친화적인 인터페이스: Streamlit을 사용하여 사용자 친화적인 인터페이스를 제공합니다.

## 기술 스택

- LangChain: 대규모 언어 모델(LLM) 기반 애플리케이션 개발을 위한 프레임워크
- LangGraph: 복잡한 워크플로우를 관리하기 위한 라이브러리
- LLM API : 고급 텍스트 생성 및 이해를 위한 API, 텍스트 생성 및 분석 API
- Neo4J: 그래프 데이터베이스
- Streamlit: 웹 애플리케이션을 쉽게 개발하기 위한 프레임워크

## 설치 및 실행 방법

1.  필수 라이브러리 설치: `requirements.txt` 파일에 정의된 라이브러리를 설치합니다.
    ```bash
    pip install -r requirements.txt
    ```
2.  환경 변수 설정: `.env` 파일에 다음 환경 변수들을 설정합니다.
    - `OPENAI_API_KEY`: OpenAI API 키
    - `GOOGLE_API_KEY`: Google Gemini API 키
    - `NEO4J_URI`: Neo4j 데이터베이스 URI (예: `bolt://localhost:7687`)
    - `NEO4J_USER`: Neo4j 데이터베이스 사용자 이름 (예: `neo4j`)
    - `NEO4J_PASSWORD`: Neo4j 데이터베이스 비밀번호 (예: `11111111`)
    - `DB_INIT_DATA_PATH`: Neo4j 초기화 데이터가 담긴 디렉토리 경로 (예: `data/initial_data`)
    - **config.py내부에 들어있던 내용은 이제 전부 .env파일로 관리됩니다.**
3. Neo4j 실행: Neo4j 데이터베이스를 설치하고 실행합니다. `.env` 파일에 설정된 URI, 사용자 이름, 비밀번호를 확인합니다. 기본 설정은 다음과 같습니다:
    - `NEO4J_URI=bolt://localhost:7687`
    - `NEO4J_USER=neo4j`
    - `NEO4J_PASSWORD=11111111`
4. Neo4j 초기 데이터 설정 : `data/initial_data` 폴더에 있는 JSON 파일들을 이용하여 Neo4j 데이터베이스를 초기화합니다. 해당 초기화를 위해서는, `db_init.py`를 실행해야 합니다.
    ```bash
    python db_init.py
    ```

5.  실행: `app.py` 파일을 실행합니다.
    ```bash
    streamlit run app.py
    ```
6. 프롬프트 확인 : `prompts` 폴더에 `story-gen-prompt-eng.yaml`, `analysis_map_prompt_eng.yaml`이 존재해야 합니다.
7. 맵 데이터 확인: `data\map` 폴더에 맵 데이터가 존재하는지 확인합니다.
8. 초기 게임 상태 확인: `data\state` 폴더에 `sample_game_state.json` 파일이 존재하는지 확인합니다.

## 파일 구조
```bash
novelist_prototype/
├── app.py                     # Streamlit 웹 애플리케이션 메인 파일
├── character.py               # 게임 캐릭터 클래스 정의
├── db_init.py                 # Neo4j 데이터베이스 초기화 스크립트
├── db.py                      # Neo4j 데이터베이스 관리 클래스 정의
├── db_utils.py                # Neo4j 데이터베이스 유틸리티 함수 정의
├── map_tools.py               # map 데이터 추출을 위한 함수
├── node.py                    # LangGraph 노드 정의
├── config.py                  # dotenv 등 환경 로드 함수
├── prompts/                   # LLM 프롬프트 YAML 파일 폴더
│   ├── story-gen-prompt-eng.yaml # 스토리 생성 프롬프트
│   └── analysis_map_prompt_eng.yaml # 맵 분석 프롬프트
├── data/                      # 게임 데이터 폴더
│   ├── map/                   # 맵 데이터 폴더
│   │   └── sample_map_data.txt # 맵 데이터 파일
│   └── state/                 # 게임 상태 데이터 폴더
│       └── sample_game_state.json # 게임 초기 상태 json 파일
├── state_graph.py             # LangGraph 상태 그래프 정의
├── states.py                  # 게임 상태 정의
├── story_chain.py             # LangChain 체인 정의
├── README.md                  # 프로젝트 설명 파일
├── .env                       # 환경변수 설정 파일
└── requirements.txt            # 프로젝트 의존성 목록
```