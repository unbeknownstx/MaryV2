# MaryV2 ElevenLabs TLS Hotfix

Fixes Windows/OpenSSL `SSLV3_ALERT_HANDSHAKE_FAILURE` by retrying the verified HTTPS request with TLS 1.2.

Security properties:
- certificate verification remains enabled
- hostname verification remains enabled
- no `CERT_NONE`
- no insecure SSL context

Install by overlaying this folder onto the MaryV2 root.

Test:

```powershell
python -m pytest tests\voice\test_elevenlabs_provider.py -q
python -m scripts.run_mobile
```

Then use Mobile > More > Voice & Avatar > Mary server only > Test Mary voice.
