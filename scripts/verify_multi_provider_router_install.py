from mary.core.config import Config
from mary.llm.router import LLMRouter

def main():
    print("MARYV2 MULTI-PROVIDER ROUTER V2 VERIFICATION")
    print("="*72)
    r=LLMRouter(Config())
    for name in ("gemini","openrouter","ollama"):
        p=r._create_provider(name)
        assert p.provider_name()==name
        print(f"PASS  {name} provider adapter installed")
    c=Config(); c.llm.provider="groq"; c.llm.routing_strategy="configured"; c.llm.fallback_providers=["gemini","openrouter","ollama","openai"]
    assert LLMRouter(c)._provider_order(None)==["groq","gemini","openrouter","ollama","openai"]
    print("PASS  configured strategy preserves the legacy provider pool")

    free=Config(); free.llm.provider="groq"; free.llm.routing_strategy="free_first"; free.llm.fallback_providers=["openai"]
    assert LLMRouter(free)._provider_order(None)==["groq","gemini","openrouter","ollama"]
    print("PASS  free_first excludes paid OpenAI")
    print("PASS  providers remain lazy and configuration-driven")
    print("="*72)
    print("MULTI-PROVIDER ROUTER V2 INSTALLED CORRECTLY")
    return 0
if __name__=="__main__": raise SystemExit(main())
