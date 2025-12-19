import gradio as gr
import random
import requests
import json
from agent import start_exam, get_next_topic, end_exam


# --- стан сесії ---
session_state = {
    "chat_history": [],
    "exam_in_progress": False,
    "current_topics": [],
    "used_topics": [],
    "current_topic": None,
    "questions_asked": 0,
    "topic_scores": {},
    "hf_api_key": None
}

MAX_QUESTIONS_PER_TOPIC = 3
MIN_GOOD_QUALITY = 6


def query_hf(messages, api_key, model="meta-llama/Llama-3.1-8B-Instruct:novita"):
    API_URL = "https://router.huggingface.co/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {"model": model, "messages": messages}
    response = requests.post(API_URL, headers=headers, json=payload, timeout=60)
    if response.status_code != 200:
        raise RuntimeError(f"HF API error: {response.status_code}, {response.text}")
    data = response.json()
    return data["choices"][0]["message"]["content"]


def finalize_exam(topic_scores, chat_history):
    final_score = sum(topic_scores.values()) / len(topic_scores) if topic_scores else 0
    feedback = []
    for topic, score in topic_scores.items():
        if score >= MIN_GOOD_QUALITY:
            feedback.append(f"Тема '{topic}' засвоєна добре")
        else:
            feedback.append(f"Тема '{topic}' потребує додаткового опрацювання")
    assistant_msg = f"Ваш фінальний результат: {final_score:.1f}/10\nВідгук по темах:\n" + "\n".join(f" - {f}" for f in feedback)
    chat_history.append({"role": "assistant", "content": assistant_msg})
    end_exam(chat_history)
    chat_history.append({"role": "assistant", "content": "Екзамен завершено."})
    return chat_history


def exam_chat(user_input, hf_api_key):
    state = session_state
    if hf_api_key:
        state["hf_api_key"] = hf_api_key.strip()

    state["chat_history"].append({"role": "user", "content": user_input})

    if not state["hf_api_key"]:
        assistant_msg = "Будь ласка, введи свій HuggingFace API Key, щоб продовжити."
        state["chat_history"].append({"role": "assistant", "content": assistant_msg})
        return state["chat_history"], ""

    if not state["exam_in_progress"]:
        # Стартуємо іспит
        state["current_topics"] = start_exam()
        random.shuffle(state["current_topics"])
        state["used_topics"] = []
        state["current_topic"] = state["current_topics"][0]
        state["used_topics"].append(state["current_topic"])
        state["exam_in_progress"] = True
        state["questions_asked"] = 0
        assistant_msg = f"Іспит розпочато.\nПерша тема: {state['current_topic']}\nПоясни основну ідею цієї теми."
        state["chat_history"].append({"role": "assistant", "content": assistant_msg})
        return state["chat_history"], ""

    # --- далі логіка іспиту, аналіз відповіді, followup і фіналізація ---
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

    if not analysis["relevant"]:
        assistant_msg = f"Відповідь не стосується теми '{state['current_topic']}'. Спробуй ще раз по суті."
        state["chat_history"].append({"role": "assistant", "content": assistant_msg})
        return state["chat_history"], ""

    score = analysis["quality"]
    state["topic_scores"][state["current_topic"]] = score
    comment = analysis.get("comment", "")
    comment += f"\nОцінка: {score}/10."
    assistant_msg = comment

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
            return finalize_exam(state["topic_scores"], state["chat_history"]), ""

    state["chat_history"].append({"role": "assistant", "content": assistant_msg})
    return state["chat_history"], ""


# Gradio UI
with gr.Blocks() as demo:
    # Markdown-блок із детальним описом
    gr.Markdown("""
# Віртуальний екзаменатор на базі LLaMA-3.1

Цей проєкт — інтерактивний **віртуальний екзаменатор**, який оцінює відповіді студента на задані теми.  
Він призначений для тестування знань користувача у будь-якій предметній області за допомогою **штучного інтелекту**.

## Основні можливості:
- Старт іспиту та генерація тем випадковим чином.
- Аналіз відповідей користувача за допомогою AI.
- Автоматична оцінка якості відповіді (0–10 балів) та надання коментаря.
- Можливість уточнювальних питань для поглибленого оцінювання.
- Підсумкова оцінка та детальний відгук по темах.
- Робота без збереження персональних даних користувачів (вводиться лише HuggingFace API Key).

## Особливості:
- **Безпека**: не зберігаємо імена, email або інші особисті дані.
- **Гнучкість**: користувач підключає власний HuggingFace API Key.
- **Адаптивність**: підлаштовується під відповіді користувача, задаючи уточнювальні питання за необхідності.
- **Візуальна інтеграція**: чатбот в інтерактивному інтерфейсі Gradio.

## Використана модель:
- **meta-llama/Llama-3.1-8B-Instruct:novita**
  - Потужна інструктивна модель для аналізу текстових відповідей та генерації уточнювальних питань.
  - Навчена на великому обсязі текстових даних, здатна давати розгорнуті коментарі та оцінки.

### Інструкція:
1. Введіть свій HuggingFace API Key.
2. Почніть іспит, натиснувши "Відправити".
3. Відповідайте на питання, надаючи короткі або розгорнуті відповіді.
4. Після завершення всіх тем отримаєте підсумкову оцінку та рекомендації.

_Цей чатбот імітує роль екзаменатора та дозволяє студенту перевірити свої знання у інтерактивній формі._
    """)

    if not session_state["chat_history"]:
        session_state["chat_history"].append({
            "role": "assistant",
            "content": "Привіт! Для початку введи свій HuggingFace API Key."
        })

    chatbot = gr.Chatbot(value=session_state["chat_history"])
    msg = gr.Textbox(placeholder="Введи відповідь або почни іспит")
    api_key_input = gr.Textbox(placeholder="Введи HuggingFace API Key", type="password")
    submit = gr.Button("Відправити")

    submit.click(exam_chat, inputs=[msg, api_key_input], outputs=[chatbot, msg])
    msg.submit(exam_chat, inputs=[msg, api_key_input], outputs=[chatbot, msg])

demo.launch()
