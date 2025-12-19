**Overview**  
This project is an **interactive AI agent** designed to simulate an examination experience for students, focusing on topics related to **Natural Language Processing (NLP)**. The agent engages users in a conversational format, presenting them with selected exam topics, analyzing their responses, and providing **real-time feedback**.

**How it works**  
The agent uses the **LLaMA 3.1 Instruct model** hosted on HuggingFace to evaluate the **relevance** and **quality** of answers, generate concise comments, and pose **follow-up questions** when necessary. Users interact entirely through a **Gradio-based web interface**, submitting responses and receiving structured feedback, including **topic scores** and **study suggestions**.

**Privacy and session management**  
No personal student information is stored. Users only provide their **HuggingFace API key** to access the model. The system tracks **current topics**, **used topics**, number of **questions asked**, and **scores**, enabling a realistic, adaptive exam simulation.

**Benefits**  
By combining advanced language model capabilities with an intuitive interface, this project provides a **safe, interactive, and realistic environment** for practicing and evaluating knowledge in NLP and related subjects, effectively simulating an actual exam scenario.

Link: <[Agent](https://huggingface.co/spaces/gdgsa/agent)>
