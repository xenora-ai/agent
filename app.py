import gradio as gr
import json
import random
import requests
from agent import start_exam, get_next_topic, end_exam


# стан сесії студента
session_state = {
    "chat_history": [],
    "student_verified": False,
    "exam_in_progress": False,
    "current_topics": [],
    "used_topics": [],
    "current_topic": None,
    "questions_asked": 0,
    "topic_scores": {},
    "email": None,
    "name": None,
    "hf_api_key": None
}

MAX_QUESTIONS_PER_TOPIC = 3
MIN_GOOD_QUALITY = 6


# функція для виклику HF API з динамічним ключем
def query_hf(messages, api_key, model="meta-llama/Llama-3.1-8B-Instruct:novita"):
    API_URL = "https://router.huggingface.co/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {"model": model, "messages": messages}
    response = requests.post(API_URL, headers=headers, json=payload, timeout=60)
    if response.status_code != 200:
        raise RuntimeError(f"HF API error: {response.status_code}, {response.text}")
    data = response.json()
    return data["choices"][0]["message"]["content"]


def finalize_exam(email, topic_scores, chat_history):
    final_score = sum(topic_scores.values()) / len(topic_scores) if topic_scores else 0

    feedback = []
    for topic, score in topic_scores.items():
        if score >= MIN_GOOD_QUALITY:
            feedback.append(f"Тема '{topic}' засвоєна добре")
        else:
            feedback.append(f"Тема '{topic}' потребує додаткового опрацювання")

    assistant_msg = f"Ваш фінальний результат: {final_score:.1f}/10\nВідгук по темах:\n" + "\n".join(f" - {f}" for f in feedback)
    chat_history.append({"role": "assistant", "content": assistant_msg})

    end_exam(email, final_score, chat_history)
    chat_history.append({"role": "assistant", "content": "Екзамен завершено."})
    return chat_history


def exam_chat(user_input, hf_api_key):
    state = session_state
    # Зберігаємо ключ користувача
    if hf_api_key:
        state["hf_api_key"] = hf_api_key.strip()

    state["chat_history"].append({"role": "user", "content": user_input})

    if not state["hf_api_key"]:
        assistant_msg = "Будь ласка, введи свій HuggingFace API Key, щоб продовжити."
        state["chat_history"].append({"role": "assistant", "content": assistant_msg})
        return state["chat_history"], ""

    # --- 1. Верифікація студента ---
    if not state["student_verified"]:
        try:
            name, email = [x.strip() for x in user_input.split(",")]
            state["name"] = name
            state["email"] = email
            state["current_topics"] = start_exam(email, name)
            random.shuffle(state["current_topics"])
            state["used_topics"] = []
            state["current_topic"] = state["current_topics"][0]
            state["used_topics"].append(state["current_topic"])
            state["student_verified"] = True
            state["exam_in_progress"] = True
            state["questions_asked"] = 0

            assistant_msg = (
                f"Іспит розпочато.\nПерша тема: {state['current_topic']}\n"
                "Поясни основну ідею цієї теми."
            )
        except Exception:
            assistant_msg = "Невірний формат або студента не знайдено. Введи: Name, Email"

        state["chat_history"].append({"role": "assistant", "content": assistant_msg})
        return state["chat_history"], ""

    # --- 2. Якщо іспит завершено ---
    if not state["exam_in_progress"]:
        return finalize_exam(state["email"], state["topic_scores"], state["chat_history"]), ""

    # --- 3. Явне "не знаю" ---
    if any(x in user_input.lower() for x in ["не знаю", "не можу", "i don't know", "can't answer"]):
        assistant_msg = f"Добре, зафіксуємо, що тема '{state['current_topic']}' не засвоєна."
        state["topic_scores"][state["current_topic"]] = 0

        next_topic = get_next_topic(state["current_topics"], state["used_topics"])
        if next_topic:
            state["current_topic"] = next_topic
            state["used_topics"].append(next_topic)
            state["questions_asked"] = 0
            assistant_msg += f"\n\nНаступна тема: {state['current_topic']}\nПоясни основну ідею цієї теми."
        else:
            state["exam_in_progress"] = False
            return finalize_exam(state["email"], state["topic_scores"], state["chat_history"]), ""

        state["chat_history"].append({"role": "assistant", "content": assistant_msg})
        return state["chat_history"], ""

    # --- 4. Аналіз відповіді ---
    state["questions_asked"] += 1
    system_prompt = f"""
Ти екзаменатор.
Поточна тема: {state['current_topic']}

Проаналізуй відповідь студента.
Відповідай ВИКЛЮЧНО JSON.
Формат:
{{
  "relevant": true або false,
  "quality": число від 0 до 10,
  "comment": "короткий коментар",
  "followup_question": "одне уточнююче питання або null"
}}
"""
    try:
        raw = query_hf([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ], api_key=state["hf_api_key"])
        analysis = json.loads(raw)
    except Exception as e:
        assistant_msg = f"Не вдалося проаналізувати відповідь. Помилка: {e}"
        state["chat_history"].append({"role": "assistant", "content": assistant_msg})
        return state["chat_history"], ""

    # --- 5. Відповідь не по темі ---
    if not analysis["relevant"]:
        assistant_msg = f"Відповідь не стосується теми '{state['current_topic']}'. Спробуй ще раз по суті."
        state["chat_history"].append({"role": "assistant", "content": assistant_msg})
        return state["chat_history"], ""

    # --- 6. Відповідь релевантна, оцінка та коментар ---
    score = analysis["quality"]
    state["topic_scores"][state["current_topic"]] = score
    comment = analysis.get("comment", "")
    comment += f"\nОцінка: {score}/10."
    assistant_msg = f"{comment}"

    # --- 7. Перевірка уточнювального питання ---
    if analysis.get("followup_question") and state["questions_asked"] < MAX_QUESTIONS_PER_TOPIC:
        assistant_msg += f"\nУточнююче питання:\n{analysis['followup_question']}"
    else:
        assistant_msg += f"\nТему '{state['current_topic']}' зараховано."
        next_topic = get_next_topic(state["current_topics"], state["used_topics"])
        if next_topic:
            state["current_topic"] = next_topic
            state["used_topics"].append(next_topic)
            state["questions_asked"] = 0
            assistant_msg += f"\n\nНаступна тема: {state['current_topic']}\nПоясни основну ідею цієї теми."
        else:
            state["exam_in_progress"] = False
            return finalize_exam(state["email"], state["topic_scores"], state["chat_history"]), ""

    state["chat_history"].append({"role": "assistant", "content": assistant_msg})
    return state["chat_history"], ""


with gr.Blocks() as demo:
    if not session_state["chat_history"]:
        session_state["chat_history"].append({
            "role": "assistant",
            "content": "Привіт! Для початку введи своє ім'я та email у форматі:\nName, Email та свій HuggingFace API Key."
        })

    chatbot = gr.Chatbot(value=session_state["chat_history"])
    msg = gr.Textbox(placeholder="Введи відповідь або Name, Email")
    api_key_input = gr.Textbox(placeholder="Введи HuggingFace API Key", type="password")
    submit = gr.Button("Відправити")

    submit.click(exam_chat, inputs=[msg, api_key_input], outputs=[chatbot, msg])
    msg.submit(exam_chat, inputs=[msg, api_key_input], outputs=[chatbot, msg])

demo.launch()
