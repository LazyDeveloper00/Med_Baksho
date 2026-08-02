from abc import ABC, abstractmethod
from typing import Any

import requests


class AIProviderStrategy(ABC):
    @abstractmethod
    def generate_response(self, question: str, context: str) -> str:
        raise NotImplementedError


class OpenRouterStrategy(AIProviderStrategy):
    def __init__(self, api_key: str, model_name: str):
        self.api_key = api_key
        self.model_name = model_name

    def generate_response(self, question: str, context: str) -> str:
        if not self.api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not configured.")
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model_name,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are the Mediবাক্স record assistant. Summarize only the supplied "
                            "patient record context. Do not diagnose, prescribe, or replace a doctor."
                        ),
                    },
                    {"role": "user", "content": f"Record context:\n{context}\n\nQuestion: {question}"},
                ],
                "temperature": 0.2,
            },
            timeout=30,
        )
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        return data["choices"][0]["message"]["content"].strip()


class HuggingFaceStrategy(AIProviderStrategy):
    def __init__(self, api_key: str, model_name: str, api_url: str = ""):
        self.api_key = api_key
        self.model_name = model_name
        self.api_url = api_url or f"https://api-inference.huggingface.co/models/{model_name}"

    def generate_response(self, question: str, context: str) -> str:
        if not self.api_key:
            raise RuntimeError("HUGGINGFACE_API_KEY is not configured.")
        prompt = (
            "You are the Mediবাক্স record assistant. Use only this record context. "
            "Do not diagnose or prescribe.\n\n"
            f"Record context:\n{context}\n\nQuestion: {question}\nAnswer:"
        )
        response = requests.post(
            self.api_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"inputs": prompt, "parameters": {"max_new_tokens": 250, "temperature": 0.2}},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list) and data and isinstance(data[0], dict):
            generated = data[0].get("generated_text", "")
            return generated[len(prompt):].strip() if generated.startswith(prompt) else generated.strip()
        if isinstance(data, dict):
            return str(data.get("generated_text") or data.get("answer") or data).strip()
        return str(data).strip()
