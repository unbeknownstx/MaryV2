# MaryV2 13.1 — Realtime Character Reference Matrix

These projects are engineering references, not Mary dependencies and not code donors. Mary keeps her own ownership/provenance architecture.

| Reference | Useful pattern | Mary 13.1 adaptation | Status |
|---|---|---|---|
| VedalAI Neuro SDK | character/game integrations exposed through bounded action/context interfaces | preserve capability boundaries rather than letting integrations become identity | architecture guidance |
| Open-LLM-VTuber | modular LLM/ASR/TTS/VAD pipeline, WebSocket realtime flow, interruption | shared realtime lifecycle, anti-echo/interruption; future streaming/VAD fits this boundary | foundation added |
| AIRI | plugin/node architecture; control plane separated from high-rate data plane; local/remote capability providers | NodeRegistry + future cloud/home node contract | foundation added |
| Mai-chan recreation | multiple producers feed one priority queue; microphone priority; anti-echo; vision describes before character interprets | AttentionBus + RealtimeInteractionCoordinator + PerceptionDirector | implemented foundation |
| kimjammer/Neuro recreation | compact example of STT/TTS/avatar/memory composition | useful baseline for keeping adapters modular | reference only |

## What Mary intentionally does differently

Mary's LLM is not her identity. Her memory, relationship, developed self, agency, growth and provenance rules remain independently represented. Realtime features are being added **around** that persistent character core.

## Next knowledge to integrate after 13.1 proves stable

1. true provider token streaming and sentence-level TTS pipelining;
2. continuous VAD/barge-in on supported clients;
3. cloud-core/home-node transport over secure networking;
4. cloud-first vision with objective observations, later local multimodal inference;
5. better embedding models/rerankers benchmarked against Mary's real recall;
6. evaluation harness using explicit Mary feedback;
7. after stronger GPU: local VLMs, larger conversational models and Mary-specific LoRA experiments.

Games/Twitch/OBS are deliberately outside this immediate sequence.
