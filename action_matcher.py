from typing import List, Optional, Tuple
from langchain_openai import OpenAIEmbeddings
import numpy as np
from config import OPENAI_API_KEY


class ActionMatcher:
    def __init__(self):
        self.embeddings = OpenAIEmbeddings(api_key=OPENAI_API_KEY)
        self.cached_embeddings = {}

    def get_embedding(self, text: str) -> List[float]:
        """텍스트의 임베딩을 반환합니다."""
        if text not in self.cached_embeddings:
            self.cached_embeddings[text] = self.embeddings.embed_query(text)
        return self.cached_embeddings[text]

    def find_best_action(
        self, user_input: str, available_actions: List[str], threshold: float = 0.7
    ) -> Optional[str]:
        """사용자 입력과 가장 유사한 action을 찾습니다."""
        if not available_actions:
            return None

        input_embedding = self.get_embedding(user_input)

        # 각 action의 임베딩 계산
        action_embeddings = [self.get_embedding(action) for action in available_actions]

        # 코사인 유사도 계산
        similarities = [
            np.dot(input_embedding, action_emb)
            / (np.linalg.norm(input_embedding) * np.linalg.norm(action_emb))
            for action_emb in action_embeddings
        ]

        best_idx = np.argmax(similarities)
        best_similarity = similarities[best_idx]

        if best_similarity >= threshold:
            return available_actions[best_idx]
        return None
