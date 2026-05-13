from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
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

# Initialize RAG vector store on startup
@app.on_event("startup")
async def startup_event():
    """Initialize the RAG vector store on application startup"""
    logger.info("Initializing RAG vector store...")
    count = initialize_vector_store()
    logger.info(f"RAG vector store initialized with {count} commands")


def build_rag_prompt(relevant_commands: list[dict]) -> str:
    """Build the system prompt with only relevant commands (RAG approach)"""
    
    commands_text = "\n".join([
        f'- "{cmd["command_name"]}" -> {cmd["technical_function"]}'
        for cmd in relevant_commands
    ])
    
    return f"""You are a command interpreter for a spreadsheet-like application called Kyra Tackle Box. Your job is to analyze user requests and map them to commands, returning both the user-friendly command names and their technical function names.

RELEVANT COMMANDS FOR THIS QUERY (retrieved via semantic search):
{commands_text}

IMPORTANT RULES:
1. ONLY use commands from the RELEVANT COMMANDS list above. Never invent new commands or function names.
2. The "user_text" must use the EXACT command name (left side, e.g., "delete Column") from the list.
3. The "technical" must use the EXACT technical function name (right side, e.g., "delete_Column_Selected") from the list.
4. If a command involves a specific cell, column, or range, use the "Goto Range" command FIRST with the cell reference in parentheses.
5. Return your response in this EXACT JSON format:
   {{"user_text": "Command1.Command2", "technical": "function1.function2"}}
6. Use the dot (.) as delimiter between commands.
7. Return ONLY the JSON object, nothing else.

CELL/RANGE HANDLING RULES:
- For operations on specific cells/columns/rows, ALWAYS start with "Goto Range(cell_reference)"
- Cell reference format: Goto Range(B3), Goto Range(C19), Goto Range(A1:A10), etc.
- The "Goto Range" command navigates to the cell, then the next command operates on it.
- The technical function for "Goto Range" is "goto_Range".

EXAMPLES WITH CELL REFERENCES:

- User: "delete column C"
  → Navigate to column C, then delete column
  Response: {{"user_text": "Goto Range(C1).delete Column", "technical": "goto_Range(C1).delete_Column_Selected"}}

- User: "add a row between C19 and C20"
  → Navigate to C19, then add row (row is inserted below)
  Response: {{"user_text": "Goto Range(C19).Add Row", "technical": "goto_Range(C19).add_Row_Below"}}

- User: "go to cell B3 and add a row"
  Response: {{"user_text": "Goto Range(B3).Add Row", "technical": "goto_Range(B3).add_Row_Below"}}

- User: "hide column F"
  Response: {{"user_text": "Goto Range(F1).hide Column", "technical": "goto_Range(F1).hide_Column_Selected"}}

- User: "delete rows 5 to 10"
  Response: {{"user_text": "Goto Range(A5:A10).Delete Row", "technical": "goto_Range(A5:A10).delete_Row_Selected"}}

- User: "make cell A1 bold"
  Response: {{"user_text": "Goto Range(A1).apply Bold", "technical": "goto_Range(A1).apply_Format_Bold"}}

- User: "sort column B ascending"
  Response: {{"user_text": "Goto Range(B1).sort A Z", "technical": "goto_Range(B1).sort_Ascending"}}

EXAMPLES WITHOUT CELL REFERENCES:

- User: "open grids, open table, apply borders"
  Response: {{"user_text": "open Grids Spot.open Table.set Borders", "technical": "open_Grids_Tab.open_Table.set_Cell_Borders"}}

- User: "copy and paste"
  Response: {{"user_text": "Copy.Paste", "technical": "copy_Selection.paste_Clipboard_Content"}}

- User: "show blue zone"
  Response: {{"user_text": "show Zone Blue", "technical": "show_Zone_Blue"}}

- User: "open grids tab"
  Response: {{"user_text": "open Grids Spot", "technical": "open_Grids_Tab"}}

If the user's request doesn't match any command in the list, respond with: {{"user_text": "UNKNOWN_COMMAND", "technical": "UNKNOWN_COMMAND"}}"""


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

class ChatResponse(BaseModel):
    user_text: str
    technical: str
    session_id: str
    message_id: str
    retrieved_commands: Optional[List[dict]] = None  # Show which commands were retrieved


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
    """Process user message using RAG to retrieve relevant commands"""
    try:
        session_id = request.session_id or str(uuid.uuid4())
        
        # Get Ollama host from env or use default
        ollama_host = os.environ.get('OLLAMA_HOST', 'http://localhost:11434')
        
        # RAG Step 1: Retrieve relevant commands using semantic search
        logger.info(f"Retrieving relevant commands for: {request.message}")
        relevant_commands = retrieve_relevant_commands(request.message, top_k=15)
        logger.info(f"Retrieved {len(relevant_commands)} relevant commands")
        
        # RAG Step 2: Build prompt with only relevant commands
        system_prompt = build_rag_prompt(relevant_commands)
        
        # RAG Step 3: Generate response using Ollama with llama3.1:8b
        client = ollama.Client(host=ollama_host)
        
        response = client.chat(
            model='llama3.1:8b',
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': request.message}
            ]
        )
        
        response_text = response['message']['content'].strip()
        
        # Remove markdown code blocks if present
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
            response_text = response_text.strip()
        
        # Parse the JSON response
        try:
            parsed = json.loads(response_text)
            user_text = parsed.get("user_text", "UNKNOWN_COMMAND")
            technical = parsed.get("technical", "UNKNOWN_COMMAND")
        except json.JSONDecodeError:
            user_text = response_text
            technical = response_text
        
        # Store user message
        user_msg = ChatMessage(
            session_id=session_id,
            role="user",
            content=request.message
        )
        user_doc = user_msg.model_dump()
        user_doc['timestamp'] = user_doc['timestamp'].isoformat()
        await db.chat_messages.insert_one(user_doc)
        
        # Store assistant response
        assistant_msg = ChatMessage(
            session_id=session_id,
            role="assistant",
            content=f"{user_text}|{technical}",
            formula=user_text
        )
        assistant_doc = assistant_msg.model_dump()
        assistant_doc['timestamp'] = assistant_doc['timestamp'].isoformat()
        await db.chat_messages.insert_one(assistant_doc)
        
        # Format retrieved commands for response (top 5 for display)
        retrieved_for_display = [
            {"name": cmd["command_name"], "function": cmd["technical_function"], "score": round(cmd["relevance_score"], 3)}
            for cmd in relevant_commands[:5]
        ]
        
        return ChatResponse(
            user_text=user_text,
            technical=technical,
            session_id=session_id,
            message_id=assistant_msg.id,
            retrieved_commands=retrieved_for_display
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
        "llm_model": "llama3.1:8b",
        "ollama_host": ollama_host
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
