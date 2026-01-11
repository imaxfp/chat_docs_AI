import os

def load_prompt(filename: str) -> str:
    path = os.path.join(os.path.dirname(__file__), "prompts", filename)
    with open(path, "r") as f:
        return f.read().strip()

USER_LOOKING_FOR_PROMPT = load_prompt("USER_LOOKING_FOR_PROMPT.txt")
USER_WANT_EXPLANATION_PROMPT = load_prompt("USER_WANT_EXPLANATION_PROMPT.txt")
RAG_FINAL_ANSWER_TEMPLATE = load_prompt("RAG_FINAL_ANSWER_TEMPLATE.txt")
SYSTEM_ASSISTANT_PROMPT = load_prompt("SYSTEM_ASSISTANT_PROMPT.txt")
