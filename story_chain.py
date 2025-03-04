# story_chain.py
from langchain_openai import ChatOpenAI
from langchain_core.prompts import load_prompt
from langchain_core.output_parsers import StrOutputParser
from operator import itemgetter


def create_story_chain():
    prompt = load_prompt("prompts/story-gen-prompt-eng.yaml")
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=1, max_tokens=2048)
    story_chain = (
        {
            "map_context": itemgetter("map_context"),
            "history": itemgetter("history"),
            "name": itemgetter("name"),
        }
        | prompt
        | llm
        | StrOutputParser()
    )
    return story_chain


def create_map_analyst():
    prompt = load_prompt("prompts/analysis_map_prompt_eng.yaml")
    # 예시: ChatGoogleGenerativeAI 사용 (Gemini 모델)
    from langchain_google_genai import ChatGoogleGenerativeAI

    llm = ChatGoogleGenerativeAI(model="gemini-2.0-pro-exp-02-05", temperature=0.5)
    map_analyst = (
        {
            "current_map": itemgetter("current_map"),
            "player_position": itemgetter("player_position"),
            "history": itemgetter("history"),
        }
        | prompt
        | llm
        | StrOutputParser()
    )
    return map_analyst
