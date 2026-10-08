# Local AI guide

The BYdoc guide is a patient-facing chat widget for account and app navigation. It uses a self-hosted [Ollama chat API](https://docs.ollama.com/api/chat) with the `llama3.2:3b` local model by default. The model classifies questions into a small set of topics; the API returns reviewed answers for those topics. Model-generated prose is never shown to patients. There is no per-message model API fee. Running the model still needs local hardware or paid hosting resources. The chat is disabled until an operator starts Ollama and enables it.

## Local setup

If Ollama is already installed on your computer, start it and run:

```powershell
ollama pull llama3.2:3b
```

Alternatively, from the repository root with Docker Desktop running, use the optional container profile:

```powershell
docker compose --profile ai up -d ollama
docker compose --profile ai exec ollama ollama pull llama3.2:3b
```

Set `AI_CHAT_ENABLED=true`, `OLLAMA_BASE_URL=http://127.0.0.1:11434`, and `OLLAMA_MODEL=llama3.2:3b` in the root `.env`, then restart the Django API. The frontend needs no API key. The widget appears on every page; sign-in is required to send questions to the model. If the model is disabled, the widget still offers account and password-reset links.

If Ollama on Windows has trouble starting a model because of GPU detection, try its documented CPU override in a separate PowerShell window:

```powershell
$env:OLLAMA_HOST = "127.0.0.1:11435"
$env:OLLAMA_LLM_LIBRARY = "cpu_avx2"
ollama serve
```

Then point `OLLAMA_BASE_URL` at `http://127.0.0.1:11435` and restart the API. Keep that Ollama window running while testing chat. See [Ollama troubleshooting](https://docs.ollama.com/troubleshooting) for other CPU/GPU options.

Ollama's port is bound to localhost in development. In AWS, run it as a **private service** reachable only from the API security group, with a persistent model volume and capacity limits. Set `OLLAMA_BASE_URL` to that private service origin in the API task. Do not expose Ollama directly to the internet. AWS compute and storage are not free. If the AI service is unavailable, the API returns a generic error and no patient record changes.

## Data and safety boundaries

- The API sends only the patient's typed message and at most six previous chat messages to Ollama. It does not fetch or attach account, profile, support, or appointment records. It does not store a chat transcript in PostgreSQL; browser state clears on reload.
- The API requires a signed-in session and CSRF protection for chat. A Redis-backed limit allows at most ten requests per account in five minutes. Input, history, output length, and model generation are bounded.
- The guide cannot book, change, or cancel appointments. Current patient web screens cover accounts; doctor discovery and booking are still in development.
- The UI asks patients not to share passwords, codes, or sensitive health details. The API gives fixed responses for common account questions and several medical and emergency phrases. Other questions go to the model for topic classification; unexpected model output falls back to a general help message. These controls are not a substitute for clinical safety review; extend language coverage, red-team the guide, and approve its content before public healthcare use.
- Do not enable model request/response logging or expose raw prompts in application logs. Give operators a way to disable chat quickly through `AI_CHAT_ENABLED=false`.

The model and Ollama API are documented by [Ollama](https://docs.ollama.com/docker). The [Llama 3.2 model page](https://ollama.com/library/llama3.2) lists the default model size and supported languages; Hindi is listed, while Bengali needs separate evaluation.
