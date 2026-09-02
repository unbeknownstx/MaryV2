# Optional model candidates

These entries are research candidates, **not dependencies** and not Mary identity.
Nothing in this directory is downloaded at application startup.

Use:

```bash
python -m scripts.fetch_model_candidate --list
python -m scripts.fetch_model_candidate qwen3-1.7b-q4km-fast-brain --download
```

Every listed artifact has a reviewed source, license, and expected SHA256. A LoRA must be paired with its exact compatible base family; a matching architecture name is not sufficient.

The first roleplay adapter candidate is intentionally a generic naturalism/roleplay experiment. It may help Mary, hurt Mary, or do nothing. `AdapterLab` exists so it is judged against Mary's own evaluation suite rather than promoted because it sounds impressive in a demo.
