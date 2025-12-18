# agent.py
import random
from datetime import datetime
import json


# Завантаження бази студентів та тем
with open("data/students.json", "r", encoding="utf-8") as f:
    students_db = json.load(f)

with open("data/topics.json", "r", encoding="utf-8") as f:
    exam_topics = json.load(f)


def start_exam(email: str, name: str) -> list[str]:
    if email not in students_db or students_db[email] != name:
        raise ValueError("Студента не знайдено у базі")
    chosen_topics = random.sample(exam_topics, 2)
    print(f"[INFO] Exam started for {name}. Topics: {chosen_topics}")
    return chosen_topics


def get_next_topic(current_topics, used_topics):
    remaining = [t for t in current_topics if t not in used_topics]
    if remaining:
        return remaining[0]
    return None


def end_exam(email: str, score: float, history: list[dict]) -> None:
    """
    Завершує іспит для студента.
    Записує результат та історію чату.
    """
    student_name = students_db.get(email, email)
    print(f"[INFO] Exam ended for {student_name}. Score: {score}")
    print("[INFO] Chat history:")
    for msg in history:
        # Додаємо datetime, якщо немає
        if "datetime" not in msg:
            msg["datetime"] = datetime.now().isoformat()
        print(msg)
