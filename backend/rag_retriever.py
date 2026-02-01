"""
RAG-based Command Retrieval using ChromaDB

This module handles:
1. Loading commands from JSON file
2. Embedding commands using sentence-transformers
3. Storing embeddings in ChromaDB vector store
4. Retrieving relevant commands for user queries
"""

import json
import chromadb
from chromadb.utils import embedding_functions
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Path to commands JSON file
COMMANDS_FILE = Path(__file__).parent / "commands.json"

# ChromaDB client (in-memory for simplicity, can switch to persistent)
chroma_client = chromadb.Client()

# Use sentence-transformers for embeddings (free, runs locally)
embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"  # Fast, good quality, ~80MB
)

# Collection for commands
collection = None


def load_commands() -> dict:
    """Load commands from JSON file"""
    with open(COMMANDS_FILE, "r") as f:
        return json.load(f)


def initialize_vector_store():
    """Initialize ChromaDB with command embeddings"""
    global collection
    
    # Delete existing collection if exists (for fresh reload)
    try:
        chroma_client.delete_collection("commands")
    except:
        pass
    
    # Create collection with embedding function
    collection = chroma_client.create_collection(
        name="commands",
        embedding_function=embedding_fn,
        metadata={"description": "Command mappings for the interpreter"}
    )
    
    # Load commands
    commands = load_commands()
    
    # Prepare data for ChromaDB
    ids = []
    documents = []
    metadatas = []
    
    for command_name, technical_function in commands.items():
        # Create a rich document for better semantic search
        # Include variations and context for better matching
        doc = f"{command_name} - {technical_function}"
        
        ids.append(command_name)  # Use command name as ID
        documents.append(doc)
        metadatas.append({
            "command_name": command_name,
            "technical_function": technical_function
        })
    
    # Add to collection
    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas
    )
    
    logger.info(f"Initialized vector store with {len(commands)} commands")
    return len(commands)


def retrieve_relevant_commands(query: str, top_k: int = 15) -> list[dict]:
    """
    Retrieve the most relevant commands for a user query
    
    Args:
        query: User's natural language query
        top_k: Number of relevant commands to retrieve
        
    Returns:
        List of relevant commands with their technical functions
    """
    global collection
    
    if collection is None:
        initialize_vector_store()
    
    # Query the collection
    results = collection.query(
        query_texts=[query],
        n_results=top_k,
        include=["metadatas", "distances"]
    )
    
    # Extract and format results
    relevant_commands = []
    if results and results["metadatas"] and results["metadatas"][0]:
        for metadata, distance in zip(results["metadatas"][0], results["distances"][0]):
            relevant_commands.append({
                "command_name": metadata["command_name"],
                "technical_function": metadata["technical_function"],
                "relevance_score": 1 - distance  # Convert distance to similarity
            })
    
    return relevant_commands


def get_all_commands() -> dict:
    """Get all commands from the JSON file"""
    return load_commands()


def reload_commands():
    """Reload commands from JSON file and re-index"""
    initialize_vector_store()
    logger.info("Commands reloaded and re-indexed")


def get_command_count() -> int:
    """Get total number of commands in the store"""
    global collection
    if collection is None:
        initialize_vector_store()
    return collection.count()
