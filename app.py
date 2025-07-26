import asyncio
from llama_index.llms.ollama import Ollama
from llama_index.core import Settings
from llama_index.core.agent.workflow import AgentWorkflow
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
import os

from llama_index.core.workflow import Context
from llama_index.core import StorageContext, load_index_from_storage

# working good enough, 42 seconds to generate respose
#model_name="llama3.2"
# working better, includes citration, 142 seconds to generate respose
#model_name="llama3.1:8b"

is_chroma_index = None

def init_settings():
    model_name = os.getenv("MODEL", "llama3.2")
    # Settings control global defaults
    if os.getenv("EMB", "HF") == "OLLAMA":
        # not working good
        Settings.embed_model = OllamaEmbedding(
            model_name=model_name
        )
    else:
        # works better
        Settings.embed_model = HuggingFaceEmbedding("BAAI/bge-small-en-v1.5")

    Settings.llm = Ollama(
        model=model_name,
        request_timeout=360.0,
        # Manually set the context window to limit memory usage
        context_window=8000,
        temperature=0.1
    )
    global is_chroma_index
    is_chroma_index = os.getenv("CHROMA_IDX")

import logging
logger = logging.getLogger("uvicorn")
STORAGE_DIR = "storage"

logging.basicConfig(level=logging.INFO)
logging.getLogger("llama_index.core.indices.utils").setLevel(logging.DEBUG)

def get_index():
    # check if storage already exists
    if not os.path.exists(STORAGE_DIR):
        return None
    # load the existing index
    logger.info(f"Loading index from {STORAGE_DIR}...")
    storage_context = StorageContext.from_defaults(persist_dir=STORAGE_DIR)
    index = load_index_from_storage(storage_context)
    logger.info(f"Finished loading index from {STORAGE_DIR}")
    return index

CHROMA_DB_PATH = "./chroma_db"
CHROMA_DB_COLLECTION = "documents"
import chromadb
from llama_index.core import VectorStoreIndex
from llama_index.vector_stores.chroma import ChromaVectorStore
def get_chroma_index():
    db = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    chroma_collection = db.get_or_create_collection(CHROMA_DB_COLLECTION)
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    index = VectorStoreIndex.from_vector_store(vector_store)
    logger.info(f"Finished loading index from {CHROMA_DB_PATH}")
    return index

from typing import Any, Optional
from llama_index.core.base.base_query_engine import BaseQueryEngine
from llama_index.core.indices.base import BaseIndex
from llama_index.core.tools.query_engine import QueryEngineTool
def create_query_engine(index: BaseIndex, **kwargs: Any) -> BaseQueryEngine:
    """
    Create a query engine for the given index.

    Args:
        index: The index to create a query engine for.
        params (optional): Additional parameters for the query engine, e.g: similarity_top_k
    """
    top_k = int(os.getenv("TOP_K", 0))
    if top_k != 0 and kwargs.get("filters") is None:
        kwargs["similarity_top_k"] = top_k

    return index.as_query_engine(**kwargs)


def get_query_engine_tool(
    index: BaseIndex,
    name: Optional[str] = None,
    description: Optional[str] = None,
    **kwargs: Any,
) -> QueryEngineTool:
    """
    Get a query engine tool for the given index.

    Args:
        index: The index to create a query engine for.
        name (optional): The name of the tool.
        description (optional): The description of the tool.
    """
    if name is None:
        name = "query_index"
    if description is None:
        description = "Use this tool to retrieve information from a knowledge base. Provide a specific query and can call the tool multiple times if necessary."
    query_engine = create_query_engine(index, **kwargs)
    tool = QueryEngineTool.from_defaults(
        query_engine=query_engine,
        name=name,
        description=description,
    )
    return tool

from citation import CITATION_SYSTEM_PROMPT, enable_citation
from dotenv import load_dotenv

def create_workflow() -> AgentWorkflow:
    load_dotenv()
    init_settings()

    if is_chroma_index is None:
        index = get_index()
    else:
        index = get_chroma_index()

    if index is None:
        raise RuntimeError(
            "Index not found! Please run `python generate.py` to index the data first."
        )
    # Create a query tool with citations enabled
    query_tool = enable_citation(get_query_engine_tool(index=index))

    # Define the system prompt for the agent
    # Append the citation system prompt to the system prompt
    system_prompt = """You are a helpful assistant"""
    system_prompt += CITATION_SYSTEM_PROMPT

    return AgentWorkflow.from_tools_or_functions(
        tools_or_functions=[query_tool],
        llm=Settings.llm,
        system_prompt=system_prompt,
    )

async def main():
    workflow = create_workflow()
    # create context
    ctx = Context(workflow)
    # run agent with context
    # Run the agent
    response = await workflow.run("Changing the installation owner", ctx=ctx)
    print(str(response))

# Run the agent
if __name__ == "__main__":
    asyncio.run(main())
