# Active development — MaryV2 12.12

Current objective: make Mary feel like a continuously running character whose
local state handles routine conversational cognition before a model is asked to
help.

Primary measurements after install:

- local reflex latency
- reservoir lookup latency
- fast cloud/local provider latency
- reflection/revision latency
- TTS synthesis latency
- playback-start latency
- total perceived latency

Live benchmark order:

1. `hey mary` (should be local reflex)
2. `how are you?` (local represented state)
3. known creator fact query (local reservoir)
4. open casual conversation (fast language cortex)
5. difficult technical task (thinking/deep route)

Do not optimize the hard-thinking path at the cost of ordinary character
responsiveness.
