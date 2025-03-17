from typing import Dict, Any, List, Optional
import json


class MapAgent:
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.current_map = None

    def load_map(self, map_id: str) -> Dict[str, Any]:
        """맵 데이터를 로드하고 파싱합니다."""
        query = """
        MATCH (m:Map {id: $map_id})
        RETURN m
        """
        result = self.db_manager.query(query, {"map_id": map_id})
        if result:
            map_data = result[0]["m"]
            self.current_map = self._parse_map_data(map_data)
            return self.current_map
        return None

    def _parse_map_data(self, map_data: Dict[str, Any]) -> Dict[str, Any]:
        """맵 데이터를 파싱하고 필요한 형식으로 변환합니다."""
        parsed = {
            "id": map_data.get("id"),
            "name": map_data.get("name"),
            "description": map_data.get("description"),
            "context": map_data.get("context"),
        }

        # locations를 문자열로 직렬화
        if "locations" in map_data:
            try:
                if isinstance(map_data["locations"], str):
                    locations = json.loads(map_data["locations"])
                else:
                    locations = map_data["locations"]
                parsed["locations_json"] = json.dumps(locations)
            except json.JSONDecodeError:
                parsed["locations_json"] = "[]"

        # map_data (ASCII 맵)는 문자열로 저장
        if "map_data" in map_data:
            parsed["map_data"] = str(map_data["map_data"])

        return parsed

    def get_location(self, location_id: str) -> Optional[Dict[str, Any]]:
        """특정 위치 정보를 반환합니다."""
        if not self.current_map:
            return None

        try:
            locations = json.loads(self.current_map.get("locations_json", "[]"))
            return next((loc for loc in locations if loc["id"] == location_id), None)
        except json.JSONDecodeError:
            return None
        except Exception as e:
            print(f"위치 정보 조회 중 오류 발생: {str(e)}")
            return None
