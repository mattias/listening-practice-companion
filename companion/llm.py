"""A language model that writes and translates sentences: a local one through Ollama, or any service that
speaks the OpenAI chat API (LM Studio, llama.cpp's server, OpenRouter, Gemini's OpenAI-compatible
endpoint, OpenAI ...) with a key."""
import json
import re

import httpx


class LLMError(Exception):
    pass


class LLM:
    def __init__(self, base_url, model, api_key="", kind="ollama", timeout=300.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.kind = kind
        self.timeout = timeout

    def _headers(self):
        return {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}

    def chat_json(self, system, user, temperature=0.8, keep_alive="2m", model=None):
        """One answer as parsed JSON. Models sometimes wrap it in text or a code fence: the object is cut out."""
        text = self._chat(system, user, temperature, keep_alive, model or self.model, json_mode=True)
        return parse_json(text)

    def chat_text(self, system, user, temperature=0.3, keep_alive="2m", model=None):
        return self._chat(system, user, temperature, keep_alive, model or self.model, json_mode=False).strip()

    def _chat(self, system, user, temperature, keep_alive, model, json_mode):
        messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": user}]
        try:
            if self.kind == "ollama":
                # Ollama's own API: thinking can be switched off (it would only spend time), and a model can be
                # told how long to stay in memory, so two models take turns on one graphics card.
                body = {"model": model, "messages": messages, "stream": False, "think": False, "keep_alive": keep_alive,
                        "options": {"temperature": temperature, "num_ctx": 8192}}
                if json_mode:
                    body["format"] = "json"
                r = httpx.post(self.base_url + "/api/chat", json=body, timeout=self.timeout)
                r.raise_for_status()
                return r.json()["message"]["content"]
            body = {"model": model, "messages": messages, "temperature": temperature}
            if json_mode:
                body["response_format"] = {"type": "json_object"}
            r = httpx.post(self.base_url + "/chat/completions", json=body, headers=self._headers(), timeout=self.timeout)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            raise LLMError(f"{e.response.status_code} {e.response.text[:200]}") from e
        except (httpx.HTTPError, KeyError, ValueError) as e:
            raise LLMError(str(e) or e.__class__.__name__) from e

    def unload(self, model=None):
        """Frees the model's memory (Ollama only; other services manage their own)."""
        if self.kind != "ollama":
            return
        try:
            httpx.post(self.base_url + "/api/chat", json={"model": model or self.model, "messages": [], "keep_alive": 0}, timeout=30)
        except httpx.HTTPError:
            pass

    def models(self):
        """Names of the models available, or [] if the service can't be asked."""
        try:
            if self.kind == "ollama":
                r = httpx.get(self.base_url + "/api/tags", timeout=5)
                return [m["name"] for m in r.json().get("models", [])]
            r = httpx.get(self.base_url + "/models", headers=self._headers(), timeout=10)
            return [m["id"] for m in r.json().get("data", [])]
        except (httpx.HTTPError, ValueError, KeyError):
            return []


def parse_json(text):
    text = text.strip()
    try:
        return json.loads(text)
    except ValueError:
        pass
    match = re.search(r"\{.*\}|\[.*\]", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except ValueError:
            pass
    raise LLMError("The model did not answer with JSON: " + text[:120])
