"""Local Ollama provider through its OpenAI-compatible endpoint."""
from __future__ import annotations
import os
from ..interface import LLMInterface, LLMResponse

class OllamaProvider(LLMInterface):
    def __init__(self, model: str | None = None, base_url: str | None = None):
        self.model=model or os.getenv("MARY_OLLAMA_MODEL","qwen3:4b")
        root=(base_url or os.getenv("MARY_OLLAMA_BASE_URL","http://localhost:11434")).rstrip("/")
        self.base_url=root
        self.client=None
    def generate(self,messages,temperature=0.7,max_tokens=2048):
        if self.client is None:
            from openai import OpenAI
            self.client=OpenAI(api_key="ollama",base_url=f"{self.base_url}/v1",timeout=120.0,max_retries=0)
        r=self.client.chat.completions.create(model=self.model,messages=[{"role":m.role,"content":m.content} for m in messages],temperature=temperature,max_tokens=max_tokens)
        c=r.choices[0]; u=getattr(r,"usage",None)
        usage={"prompt_tokens":getattr(u,"prompt_tokens",0),"completion_tokens":getattr(u,"completion_tokens",0),"total_tokens":getattr(u,"total_tokens",0)} if u else {}
        return LLMResponse(content=c.message.content or "",provider="ollama",model=self.model,finish_reason=getattr(c,"finish_reason",None),usage=usage,raw=r)
    def is_available(self): return os.getenv("MARY_OLLAMA_ENABLED","true").lower() in {"1","true","yes","on"}
    def provider_name(self): return "ollama"
    def model_name(self): return self.model
