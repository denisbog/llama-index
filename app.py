import asyncio
from llama_index.llms.ollama import Ollama
from llama_index.core import Settings
from llama_index.core.agent.workflow import AgentWorkflow
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding
import os

from llama_index.core.workflow import Context
from llama_index.core import StorageContext, load_index_from_storage



def init_settings():
    # Settings control global defaults
    Settings.embed_model = OllamaEmbedding(
        model_name="llama3.1:8b"
    )
    Settings.llm = Ollama(
        model="llama3.1:8b",
        request_timeout=360.0,
        # Manually set the context window to limit memory usage
        context_window=8000,
        temperature=0.1
    )

import logging
logger = logging.getLogger("uvicorn")
STORAGE_DIR = "storage"
logging.basicConfig(level=logging.INFO)

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
    index = get_index()
    if index is None:
        raise RuntimeError(
            "Index not found! Please run `uv run generate` to index the data first."
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

def create_simple_workflow() -> AgentWorkflow:
    load_dotenv()
    init_settings()
    index = get_index()
    if index is None:
        raise RuntimeError(
            "Index not found! Please run `uv run generate` to index the data first."
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
    )

async def main():
    #workflow = create_simple_workflow()
    workflow = create_workflow()
    # create context
    ctx = Context(workflow)
    # run agent with context
    # Run the agent
    response = await workflow.run("who is the president of the united states", ctx=ctx)
    print(str(response))

# Run the agent
if __name__ == "__main__":
    asyncio.run(main())
