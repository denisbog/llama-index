import asyncio
from llama_index.llms.ollama import Ollama
from llama_index.core import Settings
model_name="llama3.2"
#model_name="llama3.1:8b"
#model_name="llama3-chatqa:8b"
#model_name="gpt-oss:latest"
#model_name="magistral:latest"
#model_name="mistral-small3.2"

from llama_index.core.callbacks import (
    CallbackManager,
    LlamaDebugHandler,
)

llama_debug = LlamaDebugHandler(print_trace_on_end=True)
callback_manager = CallbackManager([])

Settings.llm = Ollama(
    model=model_name,
    request_timeout=360.0,
    # Manually set the context window to limit memory usage
    context_window=8000,
    temperature=0.1,
    callback_manager=callback_manager,
)

#import os
#os.environ["OPENAI_API_KEY"] = ""
#from llama_index.llms.openai import OpenAI
#Settings.llm = OpenAI(
#    #model="gpt-4o-mini",
#    model="gpt-5-mini",
#  #  callback_manager=callback_manager,
#)

from llama_index.core.agent.workflow import AgentOutput, AgentWorkflow, FunctionAgent, ReActAgent, ToolCall, ToolCallResult
from llama_index.core.workflow import Context
from ai_tools_function_agent import SimpleFunctionAgent
from ai_tools_agent_workflow import SimpleAgentWorkflow

async def record_notes(ctx: Context, notes: str, notes_title: str) -> str:
    """Useful for recording notes on a given topic. Your input should be notes with a title to save the notes under."""
    async with ctx.store.edit_state() as ctx_state:
        if "research_notes" not in ctx_state["state"]:
            ctx_state["state"]["research_notes"] = {}
        ctx_state["state"]["research_notes"][notes_title] = notes
        #ctx_state["formatted_input_with_state"] = False
    return "Notes recorded."

async def write_report(ctx: Context, report_content: str) -> str:
    """Useful for writing a report on a given topic. Your input should be a markdown formatted report."""
    async with ctx.store.edit_state() as ctx_state:
        ctx_state["state"]["report_content"] = report_content
        #ctx_state["formatted_input_with_state"] = False
    return "Report written."

async def review_report(ctx: Context, review: str) -> str:
    """Useful for reviewing a report and providing feedback. Your input should be a review of the report."""
    async with ctx.store.edit_state() as ctx_state:
        ctx_state["state"]["review"] = review
        #ctx_state["formatted_input_with_state"] = False
    return "Report reviewed."

research_agent = SimpleFunctionAgent(
    name="ResearchAgent",
    description="you are providing initial context and recording notes",
    system_prompt=(
        "You have multiple tools. Check the list of available tools with their functionalities below. You can use only the tools listed below. "
        "If notes are recorded then hand the task to the write agent. "
        "Call record notes first then hand the task to write agent. "
        "You have to record the notes, and after pass the task to the write agent."

    ),
    tools=[record_notes],
    can_handoff_to=["WriteAgent"],
)

write_agent = SimpleFunctionAgent(
    name = "WriteAgent",
    description="writes report on given topic, can be called only if record notes are provided in the current state",
    system_prompt=(
        "You have multiple tools. You can call functions multiple times as required. "
        "Call write report first then hand the task to review agent. "
        "You are the WriteAgent that can write a report on a given topic. "
        "Your report should be in a markdown format. The content should be grounded in the research notes. "
        "Once the report is written, you should get feedback at least once from the ReviewAgent."
    ),
    tools=[write_report],
    can_handoff_to=["ReviewAgent", "ResearchAgent"],
)

review_agent = SimpleFunctionAgent(
    name = "ReviewAgent",
    description="reviews a report and provides feedback",
    system_prompt=(
        "You have multiple tools. You can call functions multiple times as required. "
        "Call review report tool first passing the review of the report."
        "If review is present in the current state then hand the task to the write agent."
        "You are the ReviewAgent that can review the write report and provide feedback. "
        "Ignore small typos. "
        "Your review should either approve the current report or request changes for the WriteAgent to implement. "
        "If you have feedback that requires changes, you should hand off control to the WriteAgent to implement the changes after submitting the review."
    ),
    tools=[review_report],
    can_handoff_to=["WriteAgent"]
)

agent_workflow = SimpleAgentWorkflow(
    agents=[research_agent, write_agent, review_agent],
    root_agent = research_agent.name,
    initial_state={
        "research_notes" : {},
        "report_content" : "Not written yet.",
        "review" : "Review required.",
    }
)

async def main():
    handler = agent_workflow.run(user_msg=(
      "write a report about Moldova. "
      "Briefly describe the history, geograhpy, political climate."
    ))

    current_agent = None
    current_tool_calls = ""

    async for event in handler.stream_events():
        if (hasattr(event, "current_agent_name") and event.current_agent_name != current_agent):
            current_agent = event.current_agent_name
            print(f"\n{'='*50}")
            print(f"🤖 Agent: {current_agent}")
            print(f"\n{'='*50}")
        elif isinstance(event, AgentOutput):
            if event.response.content:
                print("📤 Output: ", event.response.content)
            if event.tool_calls:
                print("🛠️ Planning to use tools:", [call.tool_name for call in event.tool_calls])
        elif isinstance(event, ToolCallResult):
            print(f"🔧 Tool Result ({event.tool_name}):")
            print(f"   Arguments: {event.tool_kwargs}")
            print(f"   Output: {event.tool_output}")
        elif isinstance(event, ToolCall):
            print(f"🔧 Calling tool ({event.tool_name}):")
            print(f"   Arguments: {event.tool_kwargs}")

    state = await handler.ctx.store.get("state")
    print(state["report_content"])
    print("--------------------------------------------------")
    print(state["review"])

# Run the agent
if __name__ == "__main__":
   asyncio.run(main())
