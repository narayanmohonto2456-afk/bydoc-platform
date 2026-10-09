# Guided help and support chat

The BYdoc help widget guides signed-in patients through booking, account, and app questions. It also opens an explicit support-request form and shows the patient's case references and statuses. Its common answers are reviewed text and work without an AI model. An optional self-hosted [Ollama chat API](https://docs.ollama.com/api/chat) classifies other questions into bounded topics; model-generated prose is never shown to patients. The default model is `llama3.2:3b`. There is no per-message model API fee, but running it needs local hardware or paid hosting resources.

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

The guide starts with `ASSISTANT_ENABLED=true` and `AI_CHAT_ENABLED=false`. To add model topic classification, set `AI_CHAT_ENABLED=true`, `OLLAMA_BASE_URL=http://127.0.0.1:11434`, and `OLLAMA_MODEL=llama3.2:3b` in the root `.env`, then restart the Django API. The frontend needs no API key. The widget appears on every page; sign-in is required to chat or create a support request. If the model is off or unavailable, reviewed guidance and support requests still work.

If Ollama on Windows has trouble starting a model because of GPU detection, try its documented CPU override in a separate PowerShell window:

```powershell
$env:OLLAMA_HOST = "127.0.0.1:11435"
$env:OLLAMA_LLM_LIBRARY = "cpu_avx2"
ollama serve
```

Then point `OLLAMA_BASE_URL` at `http://127.0.0.1:11435` and restart the API. Keep that Ollama window running while testing chat. See [Ollama troubleshooting](https://docs.ollama.com/troubleshooting) for other CPU/GPU options.

Ollama's port is bound to localhost in development. In AWS, run it as a **private service** reachable only from the API security group, with a persistent model volume and capacity limits. Set `OLLAMA_BASE_URL` to that private service origin in the API task. Do not expose Ollama directly to the internet. AWS compute and storage are not free. If the AI service is unavailable, the guide falls back to fixed product guidance and can still create support cases.

## Data and safety boundaries

- With AI enabled, the API sends only the patient's typed message and at most six previous chat messages to Ollama. It does not fetch or attach account, profile, support, or appointment records. It does not store a chat transcript in PostgreSQL; browser state clears on reload.
- The API requires a signed-in session and CSRF protection for chat and case creation. Shared Redis limits allow at most ten chat messages per account in five minutes and five support submissions per account in an hour. Input, history, output length, and model generation are bounded.
- The guide cannot book, change, or cancel appointments. It links to the existing doctor discovery and booking page. Support cases are created only when the patient reviews and submits the separate form; chat history is never attached. Cases are stored in PostgreSQL with the existing support access controls and audit events. The widget shows only the signed-in account's case references and statuses.
- The UI asks patients not to share passwords, codes, or sensitive health details. The API gives fixed responses for common account questions and several medical and emergency phrases. Other questions go to the model for topic classification; unexpected model output falls back to a general help message. These controls are not a substitute for clinical safety review; extend language coverage, red-team the guide, and approve its content before public healthcare use.
- Do not enable model request/response logging or expose raw prompts in application logs. Operators can disable the model through `AI_CHAT_ENABLED=false` or the chat reply endpoint through `ASSISTANT_ENABLED=false`; support-case submission remains available through its separate API.

## Launch checks

Before public use, review the fixed guidance in each supported language, test emergency and clinical prompts, verify support staff can see and act on new cases, set a response-time policy, and monitor case queues. Validate Ollama capacity and timeout behavior under expected traffic if the model is enabled. The widget is asynchronous support, not a live human chat or emergency service. The broader AWS deployment, operations, and clinical review gates remain open in [the deployment guide](aws-deployment.md).

The model and Ollama API are documented by [Ollama](https://docs.ollama.com/docker). The [Llama 3.2 model page](https://ollama.com/library/llama3.2) lists the default model size and supported languages; Hindi is listed, while Bengali needs separate evaluation.
