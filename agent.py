import random
from datetime import datetime
import json


# Завантажуємо лише теми
with open("data/topics.json", "r", encoding="utf-8") as f:
    exam_topics = json.load(f)


def start_exam() -> list[str]:
    # Випадково вибираємо 2 теми
    chosen_topics = random.sample(exam_topics, 2)
    print(f"[INFO] Exam started. Topics: {chosen_topics}")
    return chosen_topics


def get_next_topic(current_topics, used_topics):
    remaining = [t for t in current_topics if t not in used_topics]
    if remaining:
        return remaining[0]
    return None


def end_exam(history: list[dict]) -> None:
    """Завершує іспит. Логує історію чату."""
    print("[INFO] Exam ended. Chat history:")
    for msg in history:
        if "datetime" not in msg:
            msg["datetime"] = datetime.now().isoformat()
        print(msg)
