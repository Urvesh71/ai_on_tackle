from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import re
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Any
import uuid
from datetime import datetime, timezone
import ollama
import json

# Import RAG retriever
from rag_retriever import (
    initialize_vector_store,
    retrieve_relevant_commands,
    get_all_commands,
    reload_commands,
    get_command_count
)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# RAG ambiguity threshold — if top-1 similarity < this, we flag the request as ambiguous
AMBIGUITY_THRESHOLD = 0.40

# Phrases that indicate the user is confirming a previously proposed plan
CONFIRM_RE = re.compile(
    r"^\s*("
    r"y|yes|yeah|yep|yup|ya|ok|okay|k|kk|sure|alright|fine|"
    r"confirm|confirmed|proceed|go|go ahead|do it|execute|run it|run|"
    r"approved|approve|correct|right|that.?s correct|that.?s right|"
    r"sounds good|looks good|perfect|great|done"
    r")"
    r"[\s\.\!\,\?]*$",
    re.IGNORECASE,
)


def is_confirmation(text: str) -> bool:
    """Return True if the user's message is a simple confirmation like 'yes', 'ok'."""
    return bool(CONFIRM_RE.match(text.strip()))


# ---------- Action counting & plan validation ----------
def split_user_actions(text: str) -> List[str]:
    """Split a user request into distinct action phrases.

    Splits on commas, 'and', 'then', '+' (case-insensitive).
    Example: "open grid, create table and apply borders"
        -> ["open grid", "create table", "apply borders"]
    """
    # Normalize separators to comma
    normalized = re.sub(r"\s+(and|then)\s+", ",", text, flags=re.IGNORECASE)
    normalized = re.sub(r"\s*\+\s*", ",", normalized)
    parts = [p.strip(" .;:!?\t") for p in normalized.split(",")]
    return [p for p in parts if p and len(p) >= 2]


def _bare_function(fn: str) -> str:
    """Strip a trailing '(...)' parameter group, leaving the bare function name."""
    return re.sub(r"\(.*\)\s*$", "", (fn or "").strip())


# Phrases that ALWAYS mean ambiguous-grid (standalone usage triggers clarify)
AMBIGUOUS_GRID_RE = re.compile(
    r"^\s*(please\s+|pls\s+)?"
    r"(create|make|new|open|add)\s+"
    r"(a\s+)?(new\s+)?grid"
    r"\s*[\.\!]?\s*$",
    re.IGNORECASE,
)


def is_ambiguous_grid_phrase(text: str) -> bool:
    """True if the user's message is a STANDALONE ambiguous grid request like
    'create grid', 'open grid', 'new grid', 'make a new grid', etc.
    (Used as a server-side pre-check before the LLM, so 8B-class models
    cannot miss the rule.)
    """
    return bool(AMBIGUOUS_GRID_RE.match(text.strip()))


def validate_plan_steps(steps: List[dict]) -> tuple[List[dict], List[dict]]:
    """Validate each step's function exists in the loaded commands catalog.

    Returns (valid_steps, invalid_steps).
    """
    catalog_funcs = set(get_all_commands().values())
    valid: List[dict] = []
    invalid: List[dict] = []
    for s in steps:
        bare = _bare_function(s.get("function", ""))
        if bare and bare in catalog_funcs:
            valid.append(s)
        else:
            invalid.append(s)
    return valid, invalid


# Initialize RAG vector store on startup
@app.on_event("startup")
async def startup_event():
    """Initialize the RAG vector store on application startup"""
    logger.info("Initializing RAG vector store...")
    count = initialize_vector_store()
    logger.info(f"RAG vector store initialized with {count} commands")


def build_rag_prompt(
    relevant_commands: list[dict],
    ambiguous: bool = False,
    pending_plan: Optional[dict] = None,
) -> str:
    """Build the system prompt with retrieved commands and instructions for the
    three response modes: single, multi, clarify.
    """

    commands_text = "\n".join(
        [
            f'- "{cmd["command_name"]}" -> {cmd["technical_function"]}'
            for cmd in relevant_commands
        ]
    )

    ambiguity_hint = ""
    if ambiguous:
        ambiguity_hint = (
            "\nNOTE: The retrieval system has LOW CONFIDENCE that any of the above "
            "commands match the user's request (possible typo or vague phrasing). "
            "Strongly prefer 'clarify' mode and ask the user to pick from suggestions.\n"
        )

    plan_context = ""
    if pending_plan:
        prior_steps = "\n".join(
            [
                f'  {s["n"]}. "{s["command"]}" -> {s["function"]}'
                for s in pending_plan.get("steps", [])
            ]
        )
        plan_context = (
            "\nCONTEXT — A plan was previously proposed to this user (they have NOT confirmed it yet):\n"
            f'Original request: "{pending_plan.get("original_request","")}"\n'
            f"Proposed steps:\n{prior_steps}\n"
            "The user's NEW message may be: (a) a modification request ('swap step 2 and 3', "
            "'remove step 1', 'change borders to red'), or (b) a completely new request. "
            "If it is a modification, return an UPDATED 'multi' plan reflecting the change. "
            "If it is a new unrelated request, treat it as fresh.\n"
        )

    return f"""You are a command interpreter for a spreadsheet-like application called Kyra Tackle Box. Your job is to analyze user requests and map them to commands.

RELEVANT COMMANDS FOR THIS QUERY (retrieved via semantic search):
{commands_text}
{ambiguity_hint}{plan_context}

You MUST respond with exactly ONE of the three JSON shapes below. Return ONLY the JSON object, nothing else.

================================================================
ABSOLUTE ANTI-HALLUCINATION RULES (read this CAREFULLY):
================================================================
- You MUST NEVER invent a command or function name. EVERY `command` and EVERY `function` you emit MUST appear LITERALLY in the RELEVANT COMMANDS list above (left side = "command", right side = function). No exceptions.
- If you cannot find a matching entry for one of the user's actions in the RELEVANT COMMANDS list, you MUST switch the whole response to "clarify" mode and ask the user which command they meant. DO NOT silently drop the action, and DO NOT make one up.
- The only exception is the cell-reference parameter inside `Goto Range(...)` / `goto_Range(...)` — the cell/range value (e.g., `A5:E12`, `C1`) is added by you, but the function name `goto_Range` itself must still appear in the list.
- Before producing a "multi" plan, mentally check: is EVERY function I'm about to emit literally present in the RELEVANT COMMANDS list? If even one is not, switch to "clarify" mode.

================================================================
MODE 1 — "single": The user's request maps to EXACTLY ONE command (one action, no cell reference required).
================================================================
JSON shape:
{{"mode":"single","user_text":"<command name>","technical":"<technical function>"}}

Use this when the request is unambiguous and is a single atomic action.

================================================================
MODE 2 — "multi": The user's request maps to TWO OR MORE commands, OR involves a cell/range navigation followed by another action.
================================================================
JSON shape:
{{"mode":"multi","steps":[
  {{"n":1,"command":"<command name>","function":"<technical function>","description":"<short human description>"}},
  {{"n":2,"command":"<command name>","function":"<technical function>","description":"<short human description>"}}
],"confirmation_message":"Please confirm this sequence is correct. Reply 'yes' to proceed, or describe any changes."}}

ACTION-COUNTING RULE (very important):
- Count the DISTINCT actions/verbs in the user's request. They are typically separated by commas (","), the word "and", the word "then", or the symbol "+".
- Your "steps" list MUST contain AT LEAST that many action steps (plus extra "Goto Range" steps for cell navigation when required).
- NEVER merge two distinct user actions into one step, even if they look related.
- Example: "open grid, create table, apply borders" = 3 distinct actions → at least 3 action steps (and 1 implicit `Goto Range(Selection)` step before the first selection-based action — see RANGE INFERENCE below).

DISAMBIGUATION HINTS:
- "open grid" / "create grid" / "new grid" → this is AMBIGUOUS. See AMBIGUITY DISAMBIGUATION rule below — you MUST ask the user whether they want to navigate to the Grids tab first.
- "go to grids tab" / "show grids tab" / "switch to grids tab" / "open Grids Spot" → unambiguous: use `open Grids Spot` → `open_Grids_Tab`.
- "create table" / "new table" / "make a table" → use `open Table` → `open_Table`. The `open_Table` function is the one that CREATES a table. Do NOT confuse with `New Grid`.
- "open table NAME" / "open the table called NAME" / "open table 'NAME'" → use `open Table` → `open_Table(NAME)` with the table's name passed as a parameter, just like cell ranges are passed to `goto_Range(...)`. Quotes are stripped from NAME.
- "apply borders" / "add borders" / "set borders" / "make borders" → use `apply Borders` (or `set Borders`) → `set_Cell_Borders`.

AMBIGUITY DISAMBIGUATION rule (for "create grid" / "open grid" / "new grid"):
- These phrases could mean EITHER (a) "Navigate to the Grids tab, then create a new grid" OR (b) "Just create a new grid in the current view". The user might have meant either.
- When the user's request CONTAINS one of these ambiguous grid phrases as a STANDALONE first action (no other actions after it that would disambiguate it), you MUST respond in "clarify" mode asking the user which interpretation they want, with TWO suggestions:
    1. {{"command":"open Grids Spot then New Grid","function":"open_Grids_Tab.create_Grid","why":"Navigate to the Grids tab first, then create a new grid."}}
    2. {{"command":"New Grid","function":"create_Grid","why":"Just create a new grid in the current view."}}
  Phrase the question as: "Do you need to navigate to the Grids tab first, or just create a new grid in the current view?"
- HOWEVER, if the user's request includes OTHER actions after the grid phrase (e.g., "create grid, create table, apply borders"), the user clearly wants to perform a workflow. In that case, do NOT ask — proceed with `New Grid` (`create_Grid`) as the first step (the most common interpretation for a workflow).
- EXCEPTION: If the user's request is an EXACT verbatim catalog command name (e.g., the user types "New Grid" or "open Grids Spot" literally — these are the EXACT left-side names from the RELEVANT COMMANDS list), do NOT trigger this ambiguity rule. Just emit the matching command directly in "single" or "multi" mode as appropriate. (Reason: they're echoing a suggestion you already gave them — they have already disambiguated.)

RANGE INFERENCE RULE (very important):
- Some actions inherently operate on a selection/range: applying borders, formatting (bold/italic/font/alignment), merge/unmerge, fill direction, sort, filter, table placement, deleting/hiding rows or columns, etc.
- If the user mentions such an action but does NOT specify a cell or range (e.g., "apply borders" with no "A5:E12"), you MUST insert an explicit `Goto Range` step BEFORE the first such action. Use the LITERAL placeholder `Selection` as the parameter, like this:
    {{"n":N,"command":"Goto Range","function":"goto_Range(Selection)","description":"Select the current range"}}
- If the user DID specify a cell/range (e.g., "in A5:E12"), use that value instead of `Selection`, e.g., `goto_Range(A5:E12)`.
- Insert the `Goto Range` step ONCE before the first selection-based action; do NOT repeat it before every following action that also uses the same selection.

CRITICAL RULES for multi:
- Each step's "command" must be the EXACT command name from the RELEVANT COMMANDS list.
- Each step's "function" must be the EXACT technical function from the list (the only thing you may add is a `(...)` parameter group for `goto_Range`).
- Step ordering must match the order the user described, with `Goto Range` inserted per the RANGE INFERENCE rule above.
- Always include the confirmation_message field exactly as shown.

================================================================
MODE 3 — "clarify": The request has a typo, is ambiguous, or none of the relevant commands clearly match.
================================================================
JSON shape:
{{"mode":"clarify","question":"<friendly question asking for clarification>","suggestions":[
  {{"command":"<command name>","function":"<technical function>","why":"<one-line reason this might be what they meant>"}}
]}}

Use this when:
- The user's text contains an obvious typo (e.g., "delte coolum")
- The request is vague or could mean multiple different commands
- None of the RELEVANT COMMANDS confidently matches

Include 2–4 suggestions ranked from most-likely to least-likely.

================================================================
EXAMPLES
================================================================

User: "copy and paste"
Response: {{"mode":"multi","steps":[{{"n":1,"command":"Copy","function":"copy_Selection","description":"Copy the current selection"}},{{"n":2,"command":"Paste","function":"paste_Clipboard_Content","description":"Paste the clipboard content"}}],"confirmation_message":"Please confirm this sequence is correct. Reply 'yes' to proceed, or describe any changes."}}

User: "create grid"
(Ambiguous standalone grid phrase → ask which interpretation.)
Response: {{"mode":"clarify","question":"Do you need to navigate to the Grids tab first, or just create a new grid in the current view?","suggestions":[{{"command":"open Grids Spot then New Grid","function":"open_Grids_Tab.create_Grid","why":"Navigate to the Grids tab first, then create a new grid."}},{{"command":"New Grid","function":"create_Grid","why":"Just create a new grid in the current view."}}]}}

User: "open table ABC"
(User wants to open an existing table named "ABC".)
Response: {{"mode":"single","user_text":"open Table(ABC)","technical":"open_Table(ABC)"}}

User: "open the table called Sales"
Response: {{"mode":"single","user_text":"open Table(Sales)","technical":"open_Table(Sales)"}}

User: "open grid, create table, apply borders"
(3 distinct actions, no cell reference → 4 steps with an inferred `Goto Range(Selection)`.)
Response: {{"mode":"multi","steps":[{{"n":1,"command":"New Grid","function":"create_Grid","description":"Create a new grid"}},{{"n":2,"command":"Goto Range","function":"goto_Range(Selection)","description":"Select the current range"}},{{"n":3,"command":"open Table","function":"open_Table","description":"Open / create a table in the selected range"}},{{"n":4,"command":"apply Borders","function":"set_Cell_Borders","description":"Apply borders to the selected cells"}}],"confirmation_message":"Please confirm this sequence is correct. Reply 'yes' to proceed, or describe any changes."}}

User: "show blue zone"
Response: {{"mode":"single","user_text":"show Zone Blue","technical":"show_Zone_Blue"}}

User: "open grid, create table in A5 to E12 and make green borders"
Response: {{"mode":"multi","steps":[{{"n":1,"command":"New Grid","function":"create_Grid","description":"Create a new grid"}},{{"n":2,"command":"Goto Range","function":"goto_Range(A5:E12)","description":"Select the range A5:E12"}},{{"n":3,"command":"open Table","function":"open_Table","description":"Open / create a table in the selected range"}},{{"n":4,"command":"apply Borders","function":"set_Cell_Borders","description":"Apply borders (green) to the selected cells"}}],"confirmation_message":"Please confirm this sequence is correct. Reply 'yes' to proceed, or describe any changes."}}

User: "delete column C"
Response: {{"mode":"multi","steps":[{{"n":1,"command":"Goto Range","function":"goto_Range(C1)","description":"Navigate to column C"}},{{"n":2,"command":"delete Column","function":"delete_Column_Selected","description":"Delete the selected column"}}],"confirmation_message":"Please confirm this sequence is correct. Reply 'yes' to proceed, or describe any changes."}}

User: "delte coolum"
Response: {{"mode":"clarify","question":"I'm not sure what you meant. Did you want to:","suggestions":[{{"command":"delete Column","function":"delete_Column_Selected","why":"Closest match to 'delte coolum'"}},{{"command":"delete Row","function":"delete_Row_Selected","why":"You may have meant a row instead"}}]}}

If nothing matches at all, return: {{"mode":"clarify","question":"I couldn't match your request to any known command. Could you rephrase?","suggestions":[]}}
"""


# Define Models
class StatusCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class StatusCheckCreate(BaseModel):
    client_name: str

class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    role: str  # 'user' or 'assistant'
    content: str
    formula: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class PlanStep(BaseModel):
    n: int
    command: str
    function: str
    description: Optional[str] = ""


class ClarifySuggestion(BaseModel):
    command: str
    function: str
    why: Optional[str] = ""


class ChatResponse(BaseModel):
    """Unified response shape supporting all three modes.

    mode == "answer"   → user_text + technical (single or executed multi)
    mode == "plan"     → steps + confirmation_message
    mode == "clarify"  → question + suggestions
    """
    mode: str  # "answer" | "plan" | "clarify"
    session_id: str
    message_id: str

    # answer mode
    user_text: Optional[str] = None
    technical: Optional[str] = None
    steps: Optional[List[PlanStep]] = None  # numbered list (also returned on answer-from-multi)

    # plan mode
    confirmation_message: Optional[str] = None

    # clarify mode
    question: Optional[str] = None
    suggestions: Optional[List[ClarifySuggestion]] = None

    # debug
    retrieved_commands: Optional[List[dict]] = None


# ---------- Pending plan persistence ----------
async def get_pending_plan(session_id: str) -> Optional[dict]:
    return await db.pending_plans.find_one({"session_id": session_id}, {"_id": 0})


async def save_pending_plan(session_id: str, steps: List[dict], original_request: str):
    await db.pending_plans.update_one(
        {"session_id": session_id},
        {
            "$set": {
                "session_id": session_id,
                "steps": steps,
                "original_request": original_request,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        },
        upsert=True,
    )


async def clear_pending_plan(session_id: str):
    await db.pending_plans.delete_one({"session_id": session_id})


def call_ollama(system_prompt: str, user_message: str, ollama_host: str) -> dict:
    """Call Ollama and parse the JSON object out of the response."""
    oclient = ollama.Client(host=ollama_host)
    model_name = os.environ.get('OLLAMA_MODEL', 'llama3.1:8b')
    response = oclient.chat(
        model=model_name,
        messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_message},
        ],
    )
    text = response['message']['content'].strip()

    # Strip markdown fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines and lines[-1].strip() == "```" else lines[1:])
        text = text.strip()

    # Extract first {...} block to be resilient against extra prose
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    # Fallback — wrap raw text
    return {"mode": "clarify", "question": text or "Sorry, I couldn't understand that.", "suggestions": []}


# Add your routes to the router instead of directly to app
@api_router.get("/")
async def root():
    return {"message": "Hello World"}

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.model_dump()
    status_obj = StatusCheck(**status_dict)
    doc = status_obj.model_dump()
    doc['timestamp'] = doc['timestamp'].isoformat()
    _ = await db.status_checks.insert_one(doc)
    return status_obj

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    status_checks = await db.status_checks.find({}, {"_id": 0}).to_list(1000)
    for check in status_checks:
        if isinstance(check['timestamp'], str):
            check['timestamp'] = datetime.fromisoformat(check['timestamp'])
    return status_checks

@api_router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Process user message with multi-turn planning + confirmation flow."""
    try:
        session_id = request.session_id or str(uuid.uuid4())
        ollama_host = os.environ.get('OLLAMA_HOST', 'http://localhost:11434')

        # Persist user message immediately
        user_msg = ChatMessage(session_id=session_id, role="user", content=request.message)
        user_doc = user_msg.model_dump()
        user_doc['timestamp'] = user_doc['timestamp'].isoformat()
        await db.chat_messages.insert_one(user_doc)

        # ----- 1) Confirmation path: user is approving a previously proposed plan -----
        pending = await get_pending_plan(session_id)
        if pending and is_confirmation(request.message):
            steps = pending.get("steps", [])
            user_text_combined = ".".join([s["command"] for s in steps])
            technical_combined = ".".join([s["function"] for s in steps])

            assistant_msg = ChatMessage(
                session_id=session_id,
                role="assistant",
                content=f"{user_text_combined}|{technical_combined}",
                formula=user_text_combined,
            )
            doc = assistant_msg.model_dump()
            doc['timestamp'] = doc['timestamp'].isoformat()
            await db.chat_messages.insert_one(doc)
            await clear_pending_plan(session_id)

            return ChatResponse(
                mode="answer",
                session_id=session_id,
                message_id=assistant_msg.id,
                user_text=user_text_combined,
                technical=technical_combined,
                steps=[PlanStep(**s) for s in steps],
            )

        # ----- 2) Fresh request (or modification of an existing plan) -----
        # ---- 2a) Hard-coded ambiguity pre-check for standalone "create grid" / "open grid" ----
        # 8B-class models can miss subtle prompt rules. Intercept here so the
        # clarify question ALWAYS fires for these specific standalone phrases.
        if is_ambiguous_grid_phrase(request.message):
            question = "Do you need to navigate to the Grids tab first, or just create a new grid in the current view?"
            suggestions = [
                ClarifySuggestion(
                    command="open Grids Spot then New Grid",
                    function="open_Grids_Tab.create_Grid",
                    why="Navigate to the Grids tab first, then create a new grid.",
                ),
                ClarifySuggestion(
                    command="New Grid",
                    function="create_Grid",
                    why="Just create a new grid in the current view.",
                ),
            ]
            await clear_pending_plan(session_id)
            assistant_msg = ChatMessage(
                session_id=session_id,
                role="assistant",
                content=f"[CLARIFY] {question}",
                formula=None,
            )
            doc = assistant_msg.model_dump()
            doc['timestamp'] = doc['timestamp'].isoformat()
            await db.chat_messages.insert_one(doc)
            return ChatResponse(
                mode="clarify",
                session_id=session_id,
                message_id=assistant_msg.id,
                question=question,
                suggestions=suggestions,
            )

        logger.info(f"Retrieving relevant commands for: {request.message}")
        relevant_commands = retrieve_relevant_commands(request.message, top_k=15)
        logger.info(f"Retrieved {len(relevant_commands)} relevant commands")

        top_score = relevant_commands[0]["relevance_score"] if relevant_commands else 0.0
        ambiguous = top_score < AMBIGUITY_THRESHOLD

        system_prompt = build_rag_prompt(
            relevant_commands=relevant_commands,
            ambiguous=ambiguous,
            pending_plan=pending,  # may be None
        )

        parsed = call_ollama(system_prompt, request.message, ollama_host)
        mode = (parsed.get("mode") or "").lower()

        retrieved_for_display = [
            {
                "name": cmd["command_name"],
                "function": cmd["technical_function"],
                "score": round(cmd["relevance_score"], 3),
            }
            for cmd in relevant_commands[:5]
        ]

        # ----- 3) Route by mode -----
        if mode == "single":
            user_text = parsed.get("user_text", "UNKNOWN_COMMAND")
            technical = parsed.get("technical", "UNKNOWN_COMMAND")

            # Validate the single function is in the catalog (no hallucination)
            bare = _bare_function(technical)
            catalog = get_all_commands()
            catalog_funcs = set(catalog.values())
            catalog_names = set(catalog.keys())
            bare_user_text = _bare_function(user_text)
            if (not bare or bare not in catalog_funcs) or (bare_user_text and bare_user_text not in catalog_names):
                # Either function is fake OR command name doesn't match catalog exactly.
                # Try to auto-correct: find the catalog entry whose function matches bare,
                # and use its EXACT left-side name as user_text.
                fixed = False
                if bare and bare in catalog_funcs:
                    for cmd_name, fn in catalog.items():
                        if fn == bare:
                            user_text = cmd_name + (user_text[len(bare_user_text):] if bare_user_text else "")
                            fixed = True
                            break
                if not fixed:
                    # Fall back to clarify with suggestions from RAG
                    suggestions = [
                        ClarifySuggestion(
                            command=cmd["command_name"],
                            function=cmd["technical_function"],
                            why=f"Available command (RAG score {round(cmd['relevance_score'], 2)})",
                        )
                        for cmd in relevant_commands[:5]
                    ]
                    question = (
                        f"I couldn't reliably map your request to a known command "
                        f"(the model suggested \"{technical}\" which doesn't exist in the catalog). "
                        "Could you pick from the suggestions below or rephrase?"
                    )
                    await clear_pending_plan(session_id)
                    assistant_msg = ChatMessage(
                        session_id=session_id,
                        role="assistant",
                        content=f"[CLARIFY] {question}",
                        formula=None,
                    )
                    doc = assistant_msg.model_dump()
                    doc['timestamp'] = doc['timestamp'].isoformat()
                    await db.chat_messages.insert_one(doc)
                    return ChatResponse(
                        mode="clarify",
                        session_id=session_id,
                        message_id=assistant_msg.id,
                        question=question,
                        suggestions=suggestions,
                        retrieved_commands=retrieved_for_display,
                    )

            assistant_msg = ChatMessage(
                session_id=session_id,
                role="assistant",
                content=f"{user_text}|{technical}",
                formula=user_text,
            )
            doc = assistant_msg.model_dump()
            doc['timestamp'] = doc['timestamp'].isoformat()
            await db.chat_messages.insert_one(doc)
            await clear_pending_plan(session_id)
            return ChatResponse(
                mode="answer",
                session_id=session_id,
                message_id=assistant_msg.id,
                user_text=user_text,
                technical=technical,
                retrieved_commands=retrieved_for_display,
            )

        if mode == "multi":
            raw_steps = parsed.get("steps", []) or []
            steps_clean: List[dict] = []
            for i, s in enumerate(raw_steps, start=1):
                steps_clean.append({
                    "n": int(s.get("n") or i),
                    "command": str(s.get("command", "")).strip(),
                    "function": str(s.get("function", "")).strip(),
                    "description": str(s.get("description", "")).strip(),
                })

            # --- Validation: catch hallucinated functions & missing actions ---
            valid_steps, invalid_steps = validate_plan_steps(steps_clean)
            user_actions = split_user_actions(request.message)
            expected_action_count = max(1, len(user_actions))

            # Plan is INVALID if:
            #   (a) any step uses a function not in the catalog (hallucination), OR
            #   (b) we have fewer valid steps than distinct actions in the user request
            #       (and the user clearly listed multiple actions).
            plan_is_incomplete = (
                len(invalid_steps) > 0
                or (expected_action_count >= 2 and len(valid_steps) < expected_action_count)
            )

            if plan_is_incomplete:
                # Build a helpful clarify response listing what we couldn't match.
                problems: List[str] = []
                if invalid_steps:
                    problems.append(
                        "The following step(s) reference a function I don't recognize: "
                        + "; ".join(
                            f'"{s["command"]}" -> {s["function"]}' for s in invalid_steps
                        )
                    )
                if expected_action_count >= 2 and len(valid_steps) < expected_action_count:
                    matched_actions = ", ".join(s["command"] for s in valid_steps) or "(none)"
                    problems.append(
                        f"I detected {expected_action_count} distinct actions in your request "
                        f"({', '.join(repr(a) for a in user_actions)}) but I could only match "
                        f"{len(valid_steps)} of them ({matched_actions})."
                    )

                question = (
                    "I couldn't reliably map every part of your request to a known command. "
                    + " ".join(problems)
                    + " Could you rephrase the unclear parts, or pick from the suggestions below?"
                )

                # Top-5 retrieved commands as suggestions (these definitely exist in the catalog)
                suggestions = [
                    ClarifySuggestion(
                        command=cmd["command_name"],
                        function=cmd["technical_function"],
                        why=f"Available command (RAG score {round(cmd['relevance_score'], 2)})",
                    )
                    for cmd in relevant_commands[:5]
                ]

                # Clear any stale plan
                await clear_pending_plan(session_id)

                assistant_msg = ChatMessage(
                    session_id=session_id,
                    role="assistant",
                    content=f"[CLARIFY] {question}",
                    formula=None,
                )
                doc = assistant_msg.model_dump()
                doc['timestamp'] = doc['timestamp'].isoformat()
                await db.chat_messages.insert_one(doc)

                return ChatResponse(
                    mode="clarify",
                    session_id=session_id,
                    message_id=assistant_msg.id,
                    question=question,
                    suggestions=suggestions,
                    retrieved_commands=retrieved_for_display,
                )

            # --- All steps are valid → renumber and proceed as a plan ---
            for idx, s in enumerate(valid_steps, start=1):
                s["n"] = idx
            steps_clean = valid_steps

            confirmation_message = parsed.get(
                "confirmation_message",
                "Please confirm this sequence is correct. Reply 'yes' to proceed, or describe any changes."
            )

            # Persist the plan for this session
            await save_pending_plan(session_id, steps_clean, request.message)

            # Log the proposal as an assistant message
            preview = "; ".join([f'{s["n"]}.{s["command"]}' for s in steps_clean])
            assistant_msg = ChatMessage(
                session_id=session_id,
                role="assistant",
                content=f"[PLAN] {preview}",
                formula=None,
            )
            doc = assistant_msg.model_dump()
            doc['timestamp'] = doc['timestamp'].isoformat()
            await db.chat_messages.insert_one(doc)

            return ChatResponse(
                mode="plan",
                session_id=session_id,
                message_id=assistant_msg.id,
                steps=[PlanStep(**s) for s in steps_clean],
                confirmation_message=confirmation_message,
                retrieved_commands=retrieved_for_display,
            )

        if mode == "clarify":
            question = parsed.get("question", "There is no such a command. Please clarify more about your desire.")
            raw_sugs = parsed.get("suggestions", []) or []
            suggestions = [
                ClarifySuggestion(
                    command=str(s.get("command", "")).strip(),
                    function=str(s.get("function", "")).strip(),
                    why=str(s.get("why", "")).strip(),
                )
                for s in raw_sugs
            ]
            # If the LLM provided no suggestions AND RAG retrieval was weak (top score is low),
            # use the exact friendly fallback message the user requested.
            if not suggestions and (not relevant_commands or relevant_commands[0]["relevance_score"] < AMBIGUITY_THRESHOLD):
                question = "There is no such a command. Please clarify more about your desire."
            assistant_msg = ChatMessage(
                session_id=session_id,
                role="assistant",
                content=f"[CLARIFY] {question}",
                formula=None,
            )
            doc = assistant_msg.model_dump()
            doc['timestamp'] = doc['timestamp'].isoformat()
            await db.chat_messages.insert_one(doc)
            # Do NOT clear pending_plan — the user may still respond to the prior plan
            return ChatResponse(
                mode="clarify",
                session_id=session_id,
                message_id=assistant_msg.id,
                question=question,
                suggestions=suggestions,
                retrieved_commands=retrieved_for_display,
            )

        # Unknown mode — fall back to clarify
        assistant_msg = ChatMessage(
            session_id=session_id,
            role="assistant",
            content="[CLARIFY] I couldn't understand the response. Please rephrase.",
            formula=None,
        )
        doc = assistant_msg.model_dump()
        doc['timestamp'] = doc['timestamp'].isoformat()
        await db.chat_messages.insert_one(doc)
        return ChatResponse(
            mode="clarify",
            session_id=session_id,
            message_id=assistant_msg.id,
            question="I couldn't understand that. Could you rephrase?",
            suggestions=[],
        )

    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/chat/history/{session_id}")
async def get_chat_history(session_id: str):
    """Get chat history for a session"""
    messages = await db.chat_messages.find(
        {"session_id": session_id},
        {"_id": 0}
    ).sort("timestamp", 1).to_list(1000)
    
    for msg in messages:
        if isinstance(msg['timestamp'], str):
            msg['timestamp'] = datetime.fromisoformat(msg['timestamp'])
    
    return {"messages": messages}

@api_router.get("/commands")
async def get_commands():
    """Get all available commands"""
    return {"commands": get_all_commands(), "total": get_command_count()}

@api_router.post("/commands/reload")
async def reload_commands_endpoint():
    """Reload commands from JSON file and re-index in vector store"""
    reload_commands()
    return {"message": "Commands reloaded successfully", "total": get_command_count()}

@api_router.get("/rag/stats")
async def get_rag_stats():
    """Get RAG system statistics"""
    ollama_host = os.environ.get('OLLAMA_HOST', 'http://localhost:11434')
    return {
        "total_commands": get_command_count(),
        "embedding_model": "all-MiniLM-L6-v2",
        "vector_store": "ChromaDB (in-memory)",
        "retrieval_top_k": 15,
        "llm_provider": "Ollama",
        "llm_model": os.environ.get('OLLAMA_MODEL', 'llama3.1:8b'),
        "ollama_host": ollama_host,
        "ambiguity_threshold": AMBIGUITY_THRESHOLD,
    }


# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
