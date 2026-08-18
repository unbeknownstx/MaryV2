import os
from unittest.mock import patch
from mary.core.config import Config
from mary.llm.router import LLMRouter

def test_router_constructs_new_provider_types():
    r=LLMRouter(Config())
    with patch.dict(os.environ,{"GEMINI_API_KEY":"x","OPENROUTER_API_KEY":"x"}):
        assert r._create_provider("gemini").provider_name()=="gemini"
        assert r._create_provider("openrouter").provider_name()=="openrouter"
    assert r._create_provider("ollama").provider_name()=="ollama"

def test_environment_provider_order(monkeypatch):
    monkeypatch.setenv("MARY_LLM_PROVIDER","groq")
    monkeypatch.setenv("MARY_LLM_FALLBACKS","gemini,openrouter,ollama,openai")
    c=Config.from_environment(); r=LLMRouter(c)
    assert r._provider_order(None)==["groq","gemini","openrouter","ollama","openai"]
