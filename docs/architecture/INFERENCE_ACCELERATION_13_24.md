# MaryV2 13.24 — Local Inference Acceleration

13.24 adds a bounded acceleration layer beneath Mary's existing cognition and compute fabric. Multi-Token Prediction (MTP) is treated as an execution optimization, never as identity, memory, provider authority, or a reason to bypass privacy/cost policy.

## Invariant

```text
Mary turn
  -> 13.17 cognitive need
  -> existing privacy/cost/provider/node eligibility
  -> local runtime/model candidate
  -> 13.24 acceleration policy
       -> normal decoding
       -> native MTP candidate
       -> future speculative methods
  -> measured local benchmark
  -> promote only a proven winner
```

A familiar model-family name is not enough to enable MTP. The target checkpoint/runtime must actually support native MTP and must initialize successfully on that node. Mary then benchmarks the accelerated path against normal decoding before promotion.

## Why this matters

For realtime conversation, lower decoding latency can reduce dead air before TTS begins. For heavier local work, improved generation throughput can free the other home node for embodiment, STT, indexing, or stream-critical work. Acceleration does not make a smaller model more intelligent; it changes how efficiently an eligible model executes.

## Current implementation

`mary.distributed.inference_acceleration.LocalInferenceAccelerationPolicy` provides:

- `auto`, `off`, and explicit `mtp` policy modes;
- bounded speculative depth (`1..8`, default `1`);
- runtime/checkpoint capability checks;
- conservative MTP family hints only for candidate discovery;
- benchmark-before-promotion selection;
- structural metrics only: latency, throughput, TTFT, acceptance rate, success rate and sample count;
- no prompt/response retention;
- no Core startup dependency.

Current vLLM documentation describes native MTP as model-dependent speculative decoding and recommends starting with a small speculative depth such as one token. Current vLLM Speculators documentation identifies native-MTP families including Qwen3-Next and Qwen3.5. These names are used only as candidate hints; local runtime proof remains mandatory.

## Environment controls

```text
MARY_LOCAL_ACCELERATION=auto        # auto | off | mtp
MARY_MTP_SPECULATIVE_TOKENS=1      # 1..8
MARY_MTP_CHECKPOINT_CAPABLE=0       # explicit local declaration when verified
MARY_VLLM_REMOTE_READY=0            # explicit declaration for an already-running vLLM service
```

Do not set `MARY_MTP_CHECKPOINT_CAPABLE=1` merely because a model name resembles a supported family. Use it only when the actual checkpoint/runtime combination is known to expose native MTP.

## Read-only diagnostic

```powershell
python scripts/check_inference_acceleration.py
python scripts/check_inference_acceleration.py --model "Qwen3.5-9B" --runtime vllm
python scripts/check_inference_acceleration.py --model "qwen3:4b" --runtime ollama
```

The Ollama example should remain `unsupported_runtime` for native vLLM-style MTP. Mary must not pretend the optimization exists where the serving runtime does not expose it.

## Promotion rule

Given baseline and candidate benchmark evidence, 13.24 selects an accelerated method only when:

1. the candidate completed at least one successful benchmark sample;
2. success rate meets the configured floor (default `0.95`);
3. throughput or latency improves by at least the configured speedup threshold (default `1.05x`);
4. the method remains inside the already-authorized local model/node route.

Until then, normal decoding remains selected.

## Hardware plan

The M1 and Windows PC should be benchmarked independently. Hardware labels do not determine the winner. A future compatible vLLM/MTP checkpoint may be useful on one machine and inappropriate on the other. The measured winner is fed into the existing node/model scheduling evidence rather than becoming a permanent architectural preference.

## Future compatible acceleration methods

13.24 intentionally leaves room for other lossless serving optimizations, including draft-model speculation, EAGLE-family methods, prompt-lookup speculation, runtime-specific KV/cache improvements, and MLX/llama.cpp acceleration techniques. They should follow the same rule: detect, measure, then promote.
