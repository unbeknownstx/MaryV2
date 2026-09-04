# MaryV2 13.3 — Start Here

**Contract:** many surfaces, many nodes, many replaceable capabilities — one Mary.

On the Mac, begin with:

```bash
cd /path/to/MaryV2
source .venv/bin/activate
python scripts/check_mac_13_3.py
```

Then validate the current Core connection before enabling optional local compute:

```bash
curl -fsS "$MARY_CORE_URL/v1/health" && echo
```

For the optional Mac llama.cpp node, follow the existing bootstrap/run scripts;
do not put model weights or secrets in Git.

13.3 details:
- `docs/releases/MARYV2_13_3_RELEASE_NOTES.md`
- `docs/research/MARYV2_13_3_RESEARCH_SYNTHESIS.md`
