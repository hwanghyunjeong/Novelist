# Novelist (실시간 상호작용 스토리텔러)

Novelist는 LangChain과 LangGraph, OpenAI API, Gemini API, 그리고 Neo4j 그래프 데이터베이스를 활용하여 구현된 실시간 상호작용 스토리텔러입니다. 

이 프로젝트는 사용자가 참여하는 유사 TRPG(Tabletop Role-Playing Game) 경험을 제공하는 것을 목표로 합니다. 

사용자는 텍스트 기반의 입력을 통해 게임에 참여하고, AI는 실시간으로 스토리를 생성하며 게임을 진행하지만, 화면에 나타나는 모든 이야기는 소설의 형태를 가집니다.

## 주요 기능

- **동적 스토리 생성**: OpenAI API와 Gemini API를 활용하여 사용자의 입력에 따라 실시간으로 변화하는 스토리를 생성합니다.
- **RAG 기반 스토리 검색**: Neo4j의 벡터 검색 기능을 활용하여 기존 스토리라인, 감정, 행동 등을 검색하고 활용합니다.
- **게임 상태 관리**: LangGraph를 사용하여 게임의 진행 상태를 효과적으로 관리합니다.
- **그래프 데이터베이스**: Neo4j를 사용하여 게임의 요소, 관계, 상태를 관리합니다.
- **사용자 친화적인 인터페이스**: Streamlit을 사용하여 사용자 친화적인 인터페이스를 제공합니다.
- **MCP 서버 지원**: MCP(Model Communication Protocol) 서버를 통한 확장성 있는 API 인터페이스를 제공합니다.
- **이미지 생성**: Gemini API를 활용하여 스토리에 맞는 장면 이미지를 실시간으로 생성합니다.

## 기술 스택

- **LangChain**: 대규모 언어 모델(LLM) 기반 애플리케이션 개발을 위한 프레임워크
- **LangGraph**: 복잡한 워크플로우를 관리하기 위한 라이브러리
- **LLM API**: 
  - OpenAI API: GPT 모델을 통한 고급 텍스트 생성
  - Gemini API: 이미지 생성 및 텍스트 처리
- **Neo4j**: 그래프 데이터베이스 및 벡터 검색 기능
- **Streamlit**: 웹 애플리케이션을 쉽게 개발하기 위한 프레임워크
- **MCP**: Model Communication Protocol, 모델 통신 프로토콜

## 설치 및 실행 방법

### 1. 필수 라이브러리 설치
```bash
pip install -r requirements.txt
```

### 2. 환경 변수 설정
`.env` 파일을 프로젝트 루트에 생성하고 다음 환경 변수들을 설정합니다:
```
OPENAI_API_KEY=your_openai_api_key
GOOGLE_API_KEY=your_google_api_key
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_neo4j_password
DB_INIT_DATA_PATH=data/initial_data
```

### 3. Neo4j 데이터베이스 설정
1. [Neo4j Desktop](https://neo4j.com/download/) 또는 [Neo4j Docker](https://neo4j.com/docs/operations-manual/current/docker/) 설치
2. 데이터베이스 생성 및 실행 (기본 설정: `bolt://localhost:7687`, 사용자: `neo4j`)
3. 필요에 따라 APOC 및 GDS 플러그인 설치 (벡터 검색 기능 필요)

### 4. 데이터베이스 초기화
초기 데이터 로드 및 벡터 인덱스 생성:
```bash
# 기본 데이터 초기화
python db_init.py

# RAG 데이터 추가
python rag_db_append.py
```

### 5. 애플리케이션 실행
#### Streamlit 앱 (기본 모드)
```bash
streamlit run app.py
```
### 6. 필수 파일 확인
- `prompts` 폴더: `story-gen-prompt-eng.yaml`, `analysis_map_prompt_eng.yaml`
- `data/map` 폴더: 맵 데이터 파일들
- `data/state` 폴더: `sample_game_state.json`

## 파일 구조

```
novelist/
├── app.py                    # 메인 Streamlit 애플리케이션
├── story_retriever.py        # 스토리 벡터 검색 기능
├── image_gen.py              # 이미지 생성 기능
├── state_graph.py            # LangGraph 기반 상태 관리
├── story_chain.py            # 스토리 생성 체인
├── config.py                 # 환경 설정
│
├── db_manager.py             # 데이터베이스 관리 클래스
├── db_init.py                # 데이터베이스 초기화
├── rag_db_append.py          # RAG 데이터 추가 스크립트
├── db_utils.py               # 데이터베이스 유틸리티 함수
│
├── data/                     # 데이터 파일
│   ├── initial_data/         # 초기 데이터 (캐릭터, 맵, 씬)
│   ├── final/                # RAG 데이터
│   ├── map/                  # 맵 데이터
│   └── state/                # 게임 상태 데이터
│
├── prompts/                  # 프롬프트 템플릿
│   ├── story-gen-prompt-eng.yaml
│   └── analysis_map_prompt_eng.yaml
│
└── requirements.txt          # 의존성 패키지 목록
```

## 사용 방법

1. 애플리케이션을 실행하면 Streamlit 웹 인터페이스가 브라우저에서 열립니다.
2. 텍스트 입력 필드에 캐릭터 행동이나 대화를 입력합니다.
3. AI가 입력을 분석하고 스토리를 생성하여 화면에 표시합니다.
4. 행동에 따라 캐릭터가 이동하거나 상태가 변경될 수 있습니다.
5. 중요한 장면에서는 Gemini API를 통해 이미지가 생성됩니다.

## 트러블슈팅

- **Neo4j 연결 오류**: 환경 변수의 URI, 사용자 이름, 비밀번호가 올바른지 확인하세요.
- **API 키 오류**: OpenAI 및 Gemini API 키가 올바르게 설정되었는지 확인하세요.
- **벡터 검색 오류**: Neo4j에 벡터 인덱스가 올바르게 생성되었는지 확인하세요.
- **Streamlit 오류**: 필요한 모든 의존성이 설치되었는지 확인하세요.

## 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다. 자세한 내용은 LICENSE 파일을 참조하세요.
```bash
```
