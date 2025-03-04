# character.py
class Character:
    def __init__(self, x, y, vision=3):
        self.x = x
        self.y = y
        self.vision = vision
        self.direction = None

    def move_continuous_by_direction(self, direction, ascii_map):
        direction_mapping = {
            "오른쪽": (1, 0),
            "왼쪽": (-1, 0),
            "위": (0, -1),
            "아래": (0, 1),
        }
        if direction not in direction_mapping:
            print(f"알 수 없는 방향: {direction}")
            return
        dx, dy = direction_mapping[direction]
        self.move_continuous(dx, dy, ascii_map)

    def move_continuous(self, dx, dy, ascii_map):
        # 간단한 이동 로직 (벽 체크 등 포함)
        while True:
            new_x = self.x + dx
            new_y = self.y + dy
            if (
                new_y < 0
                or new_y >= len(ascii_map)
                or new_x < 0
                or new_x >= len(ascii_map[new_y])
            ):
                break
            if ascii_map[new_y][new_x] == "#":
                break
            self.x = new_x
            self.y = new_y
            # 이벤트 감지, 시야 업데이트 등 추가 가능
        print(f"최종 위치: ({self.x}, {self.y})")
