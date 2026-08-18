"""Gemini provider using Google's OpenAI-compatible endpoint."""
from __future__ import annotations
import os
from ..interface import LLMInterface, LLMMessage, LLMResponse

class GeminiProvider(LLMInterface):
    def __init__(self, model: str | None = None, api_key: str | None = None):
        self.model = model or os.getenv("MARY_GEMINI_MODEL", "gemini-2.5-flash")
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.client = None
    def generate(self, messages, temperature=0.7, max_tokens=2048):
        if not self.api_key: raise RuntimeError("Gemini API key is not configured. Set GEMINI_API_KEY.")
        if self.client is None:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.api_key, base_url="https://generativelanguage.googleapis.com/v1beta/openai/", timeout=20.0, max_retries=0)
        r=self.client.chat.completions.create(model=self.model,messages=[{"role":m.role,"content":m.content} for m in messages],temperature=temperature,max_tokens=max_tokens)
        c=r.choices[0]; u=getattr(r,"usage",None)
        usage={"prompt_tokens":getattr(u,"prompt_tokens",0),"completion_tokens":getattr(u,"completion_tokens",0),"total_tokens":getattr(u,"total_tokens",0)} if u else {}
        return LLMResponse(content=c.message.content or "",provider="gemini",model=self.model,finish_reason=getattr(c,"finish_reason",None),usage=usage,raw=r)
    def is_available(self): return bool(self.api_key)
    def provider_name(self): return "gemini"
    def model_name(self): return self.model
