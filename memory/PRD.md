# LLM Command Interpreter — PRD

## Original Problem Statement
Create an LLM Application which can be learned on the JSON commands given and whenever a user asks a question, it should map the request to the JSON library and return a hierarchical formula. The app must support both single and multi-command sequences. For multi-command requests (and ambiguous / typo inputs) the app must propose a numbered plan and ask the user to confirm before producing the final formula.

## User Choices (deployment + UX)
- Hosting: User's own Ubuntu server, Dockerised, accessed over HTTP at `http://192.168.10.64`
- LLM Provider: **Local Ollama** running `llama3.1:8b` (replaced earlier Emergent Claude integration)
- Database: MongoDB Atlas (URL injected via `MONGO_URL`)
- Theme: Dark professional UI
- Confirmation mode: free-text replies (`yes`, `ok`, `proceed`, `go`, etc.); modification via natural language
- Multi-command threshold: 2 or more commands → always show plan first
- Typo / ambiguity: hybrid detection — RAG top-1 similarity < 0.40 flags ambiguity, LLM picks the suggestions

## Architecture
- **Frontend**: React 19, Tailwind, Shadcn UI, Nginx-served Docker image
- **Backend**: FastAPI + Motor (async Mongo) + Ollama Python SDK
- **RAG**: ChromaDB (in-memory) + `sentence-transformers/all-MiniLM-L6-v2`
- **LLM**: Ollama `llama3.1:8b` over `OLLAMA_HOST` env
- **DB Collections**: `chat_messages`, `status_checks`, `pending_plans`
- **Docker**: `docker-compose.yml` orchestrates frontend (Nginx) + backend (uvicorn) + joins external `prototyp-orbit-llm_web` network for Ollama access

## What's Been Implemented
### Initial MVP (Jan 2026)
- [x] Chat interface with dark professional theme
- [x] Command-to-formula mapping
- [x] RAG retrieval (ChromaDB + Sentence-Transformers)
- [x] Cell/Range navigation pattern
- [x] Single + multi-command flat output
- [x] Formula card with numbered breakdown + copy buttons
- [x] MongoDB chat history persistence
- [x] Dockerised deployment (Frontend Nginx + Backend FastAPI + compose)
- [x] Migration from Emergent Claude → local Ollama `llama3.1:8b`

### Feb 2026
- [x] Replaced `commands.json` (128 cmds) with `Tacklecommads_v1_output.json` (228 cmds, snake_case function names)
- [x] Updated `server.py` system prompt to match the new command naming (`Goto Range`, `delete_Column_Selected`, etc.)
- [x] **Multi-turn planning + confirmation flow** ✨
  - Backend produces one of three modes: `single`, `multi`, `clarify`
  - Multi-command requests return a **numbered plan** + confirmation question
  - User confirms via free-text (`yes`/`ok`/`proceed`/...) → backend pulls saved plan from `pending_plans` and emits the final formula numbered list (no LLM round-trip)
  - User can also modify via natural language (`swap step 2 and 3`) — backend re-prompts the LLM with the prior plan as context
  - **Typo / ambiguous** inputs trigger `clarify` mode with ranked suggestions; suggestions are clickable in the UI
- [x] New components: `PlanCard.js` (numbered plan + confirm hint), `ClarifyCard.js` (clickable suggestions)
- [x] Extended `FormulaCard.js` to render structured `steps[]` numbered list
- [x] HTTP-safe UUID generator in `ChatPage.js` (replaces `crypto.randomUUID()` which fails on non-HTTPS LAN deployments)

## Core Requirements (Static)
1. Map user intents to technical commands from the loaded JSON
2. Return hierarchical formula format: `Command1.Command2.Command3`
3. Support parameters in parentheses for cell/range refs: `goto_Range(A5:E12)`
4. Sequential execution order preserved
5. Multi-command (2+) MUST be confirmed by the user before final emission
6. Typos / ambiguous input MUST request clarification with suggestions

## API Shape
`POST /api/chat` → `ChatResponse`:
| mode      | populated fields                                                          |
|-----------|---------------------------------------------------------------------------|
| `answer`  | `user_text`, `technical`, optional `steps[]`                              |
| `plan`    | `steps[]`, `confirmation_message`                                          |
| `clarify` | `question`, `suggestions[] = {command, function, why}`                     |

Plus on every reply: `session_id`, `message_id`, `retrieved_commands[]`.

`pending_plans` collection: `{session_id, steps[], original_request, created_at}` — upserted when mode=`plan`, cleared on confirmation or single answer.

## Prioritized Backlog
### P1 — Next
- [ ] Frontend dedicated `/confirm` button (in addition to free-text) — wired but visible only when plan present
- [ ] LLM-driven modify: explicit support for "swap N and M", "remove step N", "change X to Y"
- [ ] Refine prompt to embed cell/range INSIDE the `function` string (so `goto_Range(A5:E12)` ships fully formed)
- [ ] Volume-mount `commands.json` in `docker-compose.yml` so swaps don't need image rebuilds

### P2 — Future
- [ ] Arithmetic formula support (SUM, AVERAGE, etc.) in RAG + prompt
- [ ] Command autocomplete in the input box
- [ ] Export chat history
- [ ] Multi-language UI

## Known issues
- Workspace `.env` uses local MongoDB; production uses MongoDB Atlas — user's `.env` overrides this in Docker
- Ollama is NOT available in this preview sandbox, so live LLM calls only work on user's deployment
- `commands.json` is currently baked into the Docker image — file swaps require `docker cp` + restart OR a volume mount (see P1)

## Test Credentials
No auth in the app — none required.
