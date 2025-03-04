# map_tools.py
import re


def extract_map_data(file_path: str):
    with open(file_path, "r", encoding="utf-8") as file:
        data = file.read()
    map_match = re.search(r"map\s*:\s*(.*)", data)
    map_name = map_match.group(1).strip() if map_match else "Unknown Map"
    ascii_map_match = re.search(r"map\s*:.*?\n(.*?)\nContext\s*:", data, re.DOTALL)
    ascii_map = ascii_map_match.group(1).strip() if ascii_map_match else ""
    context_match = re.search(r'Context\s*:\s*"(.*?)"', data, re.DOTALL)
    context = context_match.group(1).strip() if context_match else ""
    return map_name, ascii_map, context
