import asyncio
#from llama_index.llms.ollama import Ollama
from llama_index.core import Settings
#model_name="llama3.2"
#model_name="llama3.1:8b"

#Settings.llm = Ollama(
#    model=model_name,
#    request_timeout=360.0,
#    # Manually set the context window to limit memory usage
#    context_window=8000,
#    temperature=0.1
#)


import os

os.environ["OPENAI_API_KEY"] = "sk-proj..."
from llama_index.llms.openai import OpenAI
Settings.llm = OpenAI(model="gpt-4o-mini")

from llama_index.core.agent.workflow import AgentOutput, AgentWorkflow, FunctionAgent, ReActAgent, ToolCall, ToolCallResult
from llama_index.core.workflow import Context

async def record_notes(ctx: Context, notes: str, notes_title: str) -> str:
    """Useful for recording notes on a given topic. Your input should be notes with a title to save the notes under."""
    async with ctx.store.edit_state() as ctx_state:
        if "research_notes" not in ctx_state["state"]:
            ctx_state["state"]["research_notes"] = {}
        ctx_state["state"]["research_notes"][notes_title] = notes
        #ctx_state["formatted_input_with_state"] = False
    return "Nodes recorded."

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

research_agent = FunctionAgent(
    name="ResearchAgent",
    description="you are providing initial context and recording notes",
    system_prompt=(
        "You are the ResearchAgent that provides information on a given topic and then record notes on the topic. "
        "After recording the notes handle the task to the WriteAgent."

    ),
    tools=[record_notes],
    can_handoff_to=["WriteAgent"],
)

write_agent = FunctionAgent(
    name = "WriteAgent",
    description="writes report on given topic",
    system_prompt=(
        "You are the WriteAgent that can write a report on a given topic. "
        "Your report should be in a markdown format. The content should be grounded in the research notes. "
        "Once the report is written, you should get feedback at least once from the ReviewAgent."
    ),
    tools=[write_report],
    can_handoff_to=["ReviewAgent", "ResearchAgent"],
)

review_agent = FunctionAgent(
    name = "ReviewAgent",
    description="reviews a report and provides feedback",
    system_prompt=(
        "You are the ReviewAgent that can review the write report and provide feedback. "
        "Your review should either approve the current report or request changes for the WriteAgent to implement. "
        "If you have feedback that requires changes, you should hand off control to the WriteAgent to implement the changes after submitting the review."
    ),
    tools=[review_report],
    can_handoff_to=["WriteAgent"]
)

agent_workflow = AgentWorkflow(
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

# Run the agent
if __name__ == "__main__":
   asyncio.run(main())
