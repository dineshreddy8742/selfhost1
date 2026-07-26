# Dailsmart AI

**The Voice AI Platform** — build production voice agents with a visual drag-and-drop workflow builder. From zero to a working bot in under 2 minutes.

## 🚀 Get Started

##### Setup Dailsmart AI on your Local Machine

Ensure you have Docker and Docker Compose installed. Then start the stack:

```bash
docker compose up -d
```

Once running, open [http://localhost:3010](http://localhost:3010) in your browser.

### 🎙️ Your First Voice Bot

1. Open [http://localhost:3010](http://localhost:3010) in your browser.
2. Pick **Inbound** or **Outbound**, name your bot (e.g. _Lead Qualification_), and describe the usecase.
3. Click **Web Call** to start talking directly to your bot.

> 🔑 **No API keys needed.** Dailsmart AI can run with its own LLM / TTS / STT stack, or you can connect your own keys for LLM, TTS, STT, or Telephony (e.g. Twilio, Vonage, Telnyx) anytime.

## Features

### Voice Capabilities
- **Telephony**: Integrated support for Twilio, Vonage, Vobiz, Cloudonix, and others, with call transfer support.
- **Low Latency**: Optimized for real-time processing and low-latency conversation flow.
- **Custom Providers**: Easily swap out STT, LLM, or TTS models to use your preferred options.

### Developer Experience
- **Zero Config**: Local keys automatically generated for quick prototyping.
- **Docker-First**: Fully containerized environment for predictable local dev and staging.
- **Customizable Pipeline**: Python backend using FastAPI allows deep customization of conversation states.

### Testing & Verification
- **Test Mode**: Safe testing environment that doesn't impact production data or telephony charges.
- **Interactive Playground**: Place test web calls directly from the browser editor.
