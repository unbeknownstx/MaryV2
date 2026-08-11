# MaryV1

MaryOS — a persistent AI character platform with voice, memory, tools, and avatar integration.

## Project overview

MaryV1 is a Python CLI-based AI character named Mary. She runs as an interactive terminal conversation loop. The system is fully rule-based and requires **no external API keys or paid services** in its current form.

## Architecture

| Module | File | Description |
|---|---|---|
| Personality | `core/personality.py` | Loads Mary's name, version, and trait scores from `data/personality.json` |
| State | `core/state.py` | Tracks awake/sleep, emotion, mood, and current task |
| Memory | `core/memory.py` | Persistent conversation memory stored in `data/memories.json` |
| UserModel | `core/user_model.py` | Persistent user profile stored in `data/user_profile.json` |
| IntentDetector | `core/intents.py` | Rule-based keyword intent classifier |
| Brain | `core/brain.py` | Routes events to the correct response strategy |
| ResponseGenerator | `core/response.py` | Produces text responses for each intent |
| EventManager | `core/event_manager.py` | Pub/sub event bus |
| MemoryListener | `core/memory_listener.py` | Subscribes to events and persists conversation turns |
| Event | `core/events.py` | Event data class with type, data, and timestamp |
| Reflection | `core/reflection.py` | Empty stub — future self-reflection system |
| Knowledge | `core/knowledge.py` | Empty stub — future knowledge retrieval system |
| Speech | `core/speech.py` | Empty stub — future voice system |
| Tools | `core/tools.py` | Empty stub — future tool-use system |
| Avatar | `core/avatar.py` | Stub placeholder (currently mirrors Event class) |
| Config | `core/config.py` | OpenAI key loader — not imported by main; reserved for future LLM integration |

## Data files

- `data/personality.json` — Mary's name, version, creator, and trait scores
- `data/memories.json` — Persistent conversation history
- `data/user_profile.json` — User name, goals, interests, learning style
- `knowledge/` — Topic-specific knowledge JSON files (anime, history, math, science, etc.)

## How to run

```
python main.py
```

The app starts an interactive terminal loop. Type `exit` to quit.

## Dependencies

None. The current version uses Python standard library only (`json`, `os`, `datetime`).

`requirements.txt` is intentionally empty.

## Future roadmap (not yet implemented)

- Local or free LLM integration (replace rule-based responses)
- Voice input/output
- VTuber avatar
- Streaming capabilities
- Real-world knowledge retrieval
- Perception system

## User preferences

- No paid API keys or external API dependencies for the core loop
- Preserve all existing systems — do not remove or rewrite stubs
- Keep the rule-based architecture intact as the foundation
- Target: browser-accessible Python terminal app on Replit
