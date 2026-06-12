import random
import time


MOCK_RESPONSES = {
    "default": [
        "The AI agent is running successfully with a mock LLM response.",
        "Your question was received by the production agent.",
        "This offline response can be replaced with an OpenAI or Anthropic call.",
    ],
    "docker": [
        "A container packages an application and its dependencies for consistent execution."
    ],
    "deploy": [
        "Deployment makes an application available on a server or cloud platform."
    ],
    "health": ["All agent systems are operational."],
}


def ask(question: str, delay: float = 0.1) -> str:
    time.sleep(delay + random.uniform(0, 0.05))
    question_lower = question.lower()
    for keyword, responses in MOCK_RESPONSES.items():
        if keyword in question_lower:
            return random.choice(responses)
    return random.choice(MOCK_RESPONSES["default"])


def ask_stream(question: str):
    for word in ask(question).split():
        time.sleep(0.05)
        yield word + " "
