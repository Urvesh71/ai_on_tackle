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
from emergentintegrations.llm.chat import LlmChat, UserMessage

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

# Command mapping JSON data
COMMAND_MAPPING = {
    "Top": "verticalAlignTop",
    "Middle": "verticalAlignMiddle",
    "Bottom": "verticalAlignBottom",
    "Left": "textAlignLeft",
    "Center": "textAlignCenter",
    "Right": "textAlignRight",
    "Toggle Favorite": "toggleFavoriteProcess",
    "ScreenShot": "takeScreenshot",
    "Full Screen": "fullScreen",
    "Copy": "copy",
    "Cut": "cut",
    "Paste": "paste",
    "Merge": "merge",
    "Add Comment": "addComment",
    "Delete Comment": "deleteComment",
    "Go to": "goTo",
    "Fill Right": "fillDirectionRight",
    "Fill Down": "fillDirectionDown",
    "Fill Up": "fillDirectionUp",
    "Fill Left": "fillDirectionLeft",
    "Series": "toggleSeriesDialogVisibility",
    "Bold": "bold",
    "Clear Style": "clearStyle",
    "English": "setLanguageEnglish",
    "Deutsch": "setLanguageDeutsch",
    "Log out": "logout",
    "Profile": "toggleProfileDialog",
    "Add Row": "addRow",
    "Delete Row": "deleteRow",
    "Move Row Up": "moveRowUp",
    "Move Row Down": "moveRowDown",
    "Add Arrow": "addArrow",
    "Delete Arrow": "deleteArrow",
    "Add Column": "addColumn",
    "Delete Column": "deleteColumn",
    "Move Column Right": "moveColumnRight",
    "Move Column Left": "moveColumnLeft",
    "Players": "showPlayersTab",
    "Processes": "showProcessesTab",
    "Action Flow": "toggleProcessFlow",
    "teams": "showTeamsTab",
    "Sheets": "showSheetsTab",
    "New Sheet": "addSheet",
    "Quick Acces Toolbar": "quickAccessToolbar",
    "Blue Zone": "showRedZone",
    "Game Zone": "showGameZone",
    "New Process": "newNormalProcess",
    "New Posting Process": "newPostingProcess",
    "New Grid": "newGrid",
    "Open Process/Grid": "open",
    "New Folder": "newFolder",
    "Rename Process/Grid": "renameProcess",
    "Toggle Expand": "expandItem",
    "Trash": "showTrash",
    "Hide Trash": "hideTrash",
    "Restore": "restore",
    "New Player": "newPlayer",
    "Rename Player": "renamePlayer",
    "Rename Sheet": "editSheet",
    "Font Size": "fontSize",
    "Width": "width",
    "Height": "height",
    "Add Player": "addPlayer",
    "Edit Player": "editPlayer",
    "Hide Row": "updateVisibilityHideRow",
    "Hide Column": "updateVisibilityHideColumn",
    "Auto Layout": "autoLayout",
    "Toggle Action Flow lines": "toggleProcessFlowLines",
    "Add Action Flow Arrow": "addProcessFlowArrow",
    "Circle Type": "changeCircleType",
    "Table": "openTable",
    "Toggle Gridlines": "toggleGridlines",
    "General": "setDataTypeGeneral",
    "Number": "setDataTypeNumber",
    "Currency": "setDataTypeCurrency",
    "ShortDate": "setDataTypeShortDate",
    "LongDate": "setDataTypeLongDate",
    "Time": "setDataTypeTime",
    "Fraction": "setDataTypeFraction",
    "Text": "setDataTypeText",
    "Percentage": "setDataTypePercentage",
    "Name Manger": "openNameManager",
    "Name Range": "openAddNameRange",
    "Process From SAP": "addProcessFromCycle",
    "Rename Table": "renameTable",
    "Toggle Auto Append": "toggleAutoAppend",
    "Toggle Is Column Formula": "toggleIsColumnFormula",
    "Sort A Z": "sortAsc",
    "Sort Z A": "sortDesc",
    "Filter Table": "filter",
    "Open Filter": "openFilter",
    "Clear Filter": "clearFilter",
    "Formula Box": "formulaBox",
    "Pink Zone": "blueZone",
    "Grids": "showGridsTab",
    "Business Case": "showBusinessTab",
    "Fetch Grid Data": "fetchGridData",
    "Duplicate sheet": "duplicateSheet",
    "Unmerge": "unmerge",
    "Watermark Visibility": "setWatermarkVisibility",
    "Start Style": "startStyles",
    "Load Satellite": "loadSatellite",
    "Transfer To Grid": "transferToGrid",
    "Borders": "borders",
    "Stream": "showStreamsTab",
    "Logzone": "showLogzone",
    "Unhide rows": "updateVisibilityUnhideRows",
    "Unhide columns": "updateVisibilityUnhideColumns",
    "Delete": "delete",
    "Delete Sheet": "deleteSheet",
    "Delete Process": "deleteProcess",
    "Delete Grid": "deleteGrid",
    "Delete Player": "deletePlayer",
    "Lock Range Selection": "lockRangeSelection",
    "Unlock Range Selection": "unlockRangeSelection",
    "Lock Format Cells": "lockFormating",
    "Unlock Format Cells": "unlockFormating",
    "Lock Cells": "lockCellsProtection",
    "Unlock Cells": "unlockCellsProtection",
    "Hide Cells Content": "hideCellsContent",
    "Unhide Cells Content": "unhideCellsContent",
    "Clear Protection": "clearProtections",
    "Lock Sort": "lockSortProtection",
    "Unlock Sort": "unlockSortProtection",
    "Hide Formula Visiblity": "hideFormulaVisibility",
    "Unhide Formula Visiblity": "unhideFormulaVisibility",
    "Open Protection Permissions": "togglePermissionMatrix",
    "Open Add Corner Dialog": "showAddCornerDialog"
}

# System prompt for the LLM
SYSTEM_PROMPT = """You are a command interpreter for a spreadsheet-like application. Your job is to analyze user requests and map them to commands, returning both the user-friendly command names and their technical function names.

AVAILABLE COMMANDS (Format: "Command Name" -> technicalFunctionName):
""" + "\n".join([f'- "{key}" -> {value}' for key, value in COMMAND_MAPPING.items()]) + """

RULES:
1. Identify distinct actions from the user's request
2. Map each action to BOTH:
   - The command name (human-readable key)
   - The technical function name (the value)
3. Return your response in this EXACT JSON format:
   {"user_text": "Command1.Command2.Command3", "technical": "function1.function2.function3"}
4. If a command requires parameters (like cell ranges), append them in parentheses to BOTH: CommandName(param) and functionName(param)
5. Commands are executed in order they appear
6. Use the dot (.) as delimiter between commands
7. Return ONLY the JSON object, nothing else. No explanations, no additional text.

EXAMPLES:
- User: "go to grids, create table, apply borders"
  Response: {"user_text": "Grids.Table.Borders", "technical": "showGridsTab.openTable.borders"}

- User: "delete row, hide column, sort data"
  Response: {"user_text": "Delete Row.Hide Column.Sort A Z", "technical": "deleteRow.updateVisibilityHideColumn.sortAsc"}

- User: "copy and paste"
  Response: {"user_text": "Copy.Paste", "technical": "copy.paste"}

- User: "show grids"
  Response: {"user_text": "Grids", "technical": "showGridsTab"}

- User: "go to blue zone, open grids, add corner dialog for Sheet1$E$10:$G$20"
  Response: {"user_text": "Pink Zone.Grids.Open Add Corner Dialog(Sheet1$E$10:$G$20)", "technical": "blueZone.showGridsTab.showAddCornerDialog(Sheet1$E$10:$G$20)"}

If the user's request doesn't match any command, respond with: {"user_text": "UNKNOWN_COMMAND", "technical": "UNKNOWN_COMMAND"}"""


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
    """Process user message and return command formula"""
    try:
        session_id = request.session_id or str(uuid.uuid4())
        api_key = os.environ.get('EMERGENT_LLM_KEY')
        
        if not api_key:
            raise HTTPException(status_code=500, detail="LLM API key not configured")
        
        # Initialize the chat with Claude
        chat = LlmChat(
            api_key=api_key,
            session_id=f"command-{session_id}",
            system_message=SYSTEM_PROMPT
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        
        # Create user message
        user_message = UserMessage(text=request.message)
        
        # Get response from Claude
        formula = await chat.send_message(user_message)
        formula = formula.strip()
        
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
            content=formula,
            formula=formula
        )
        assistant_doc = assistant_msg.model_dump()
        assistant_doc['timestamp'] = assistant_doc['timestamp'].isoformat()
        await db.chat_messages.insert_one(assistant_doc)
        
        return ChatResponse(
            formula=formula,
            session_id=session_id,
            message_id=assistant_msg.id
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
    return {"commands": COMMAND_MAPPING}


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
