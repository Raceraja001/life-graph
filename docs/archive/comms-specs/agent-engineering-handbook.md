# Agent Engineering Handbook

> **Purpose:** Reference document for building the Life Graph AI agent system.
> Techniques extracted from 8 open-source repos + 1 course.
> **Generated:** 05 Jul 2026 | **For:** Any Antigravity instance building agents

---

## Quick Reference — What to Steal From Where

| Technique | Source Repo | Relevance |
|:----------|:-----------|:----------|
| Agent handoff (return Agent) | OpenAI Swarm | Chief → specialist routing |
| Memory pipeline (extract → consolidate → retrieve) | Mem0 | Life Graph core memory |
| Dependency injection + typed outputs | PydanticAI | All agent tool interfaces |
| State machine orchestration + checkpoints | LangGraph | Task execution pipeline |
| OS-inspired memory (RAM/disk) + self-editing | Letta (MemGPT) | Life Graph memory hierarchy |
| Role-based teams + delegation tools | CrewAI | Agent team structure |
| Code-as-action (agent writes Python) | Smolagents | Advanced tool execution |
| Auto prompt optimization (BootstrapFewShot) | DSPy | Prompt registry auto-tuning |
| 10 design patterns curriculum | MS AI Agents | Architecture reference |

---

# Part 1: Orchestration Patterns

## 1.1 Agent Handoff — OpenAI Swarm

**Repo:** github.com/openai/swarm (~500 LOC total)
**Key insight:** An agent returns another Agent object to transfer control. That's the entire handoff mechanism.

### Core Types
```python
class Agent:
    name: str = "Agent"
    model: str = "gpt-4o"
    instructions: Union[str, Callable]  # Static or dynamic system prompt
    functions: List[Callable] = []       # Tools
    parallel_tool_calls: bool = True

class Response:
    messages: List[dict]           # Conversation history
    agent: Agent                   # Last active agent
    context_variables: dict        # Shared state

class Result:
    value: str = ""                # String result
    agent: Agent = None            # If set → handoff!
    context_variables: dict = {}   # State updates
```

### The Entire Orchestration Loop (~30 lines)
```python
def run(self, agent, messages, context_variables={}, max_turns=float("inf")):
    active_agent = agent
    history = copy.deepcopy(messages)
    
    while len(history) - init_len < max_turns:
        # 1. Call LLM with current agent's instructions + tools
        completion = self.get_chat_completion(active_agent, history, context_variables)
        message = completion.choices[0].message
        history.append(message)
        
        # 2. No tool calls → done
        if not message.tool_calls:
            break
        
        # 3. Execute each tool call
        for tool_call in message.tool_calls:
            func = {f.__name__: f for f in active_agent.functions}[tool_call.function.name]
            args = json.loads(tool_call.function.arguments)
            
            # Inject context_variables if function accepts it
            if "context_variables" in inspect.signature(func).parameters:
                args["context_variables"] = context_variables
            
            raw_result = func(**args)
            result = self.handle_function_result(raw_result)
            
            # 4. HANDOFF: if function returned an Agent, switch!
            if result.agent:
                active_agent = result.agent
            
            context_variables.update(result.context_variables)
            history.append({"role": "tool", "content": result.value})
    
    return Response(messages=history, agent=active_agent, context_variables=context_variables)
```

### Handoff Pattern
```python
refund_agent = Agent(name="Refund Agent", instructions="Process refunds.")
sales_agent = Agent(name="Sales Agent", instructions="Handle sales.")

def transfer_to_refund():
    """Transfer to the refund department."""
    return refund_agent  # ← THIS IS THE HANDOFF

triage = Agent(
    name="Triage",
    instructions="Route customer to the right department.",
    functions=[transfer_to_refund, transfer_to_sales]
)

response = client.run(agent=triage, messages=[{"role": "user", "content": "I want a refund"}])
# response.agent.name == "Refund Agent"
```

### Tool Auto-Schema (function_to_json)
```python
def function_to_json(func):
    """Convert Python function → OpenAI tool JSON using inspect"""
    type_map = {str: "string", int: "integer", float: "number", bool: "boolean"}
    sig = inspect.signature(func)
    parameters = {}
    for name, param in sig.parameters.items():
        if name == "context_variables": continue
        parameters[name] = {"type": type_map.get(param.annotation, "string")}
    
    return {
        "type": "function",
        "function": {
            "name": func.__name__,
            "description": func.__doc__ or "",
            "parameters": {"type": "object", "properties": parameters}
        }
    }
```

### What to Adopt
- **Handoff pattern** for Chief → specialist routing
- **context_variables** as shared state between agents
- **function_to_json** for auto-generating tool schemas
- **Dynamic instructions** (callable that receives context)

---

## 1.2 State Machine Orchestration — LangGraph

**Repo:** github.com/langchain-ai/langgraph
**Key insight:** Model agent workflows as directed graphs with explicit state, checkpointing, and human-in-the-loop.

### State Definition with Reducers
```python
from typing import Annotated, TypedDict
from langgraph.graph.message import add_messages
import operator

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]  # Append reducer
    step_count: Annotated[int, operator.add]  # Accumulate reducer
    current_agent: str                        # Last-write-wins (default)
```

### Graph Construction
```python
from langgraph.graph import StateGraph, START, END

def call_llm(state):
    response = llm.invoke(state["messages"])
    return {"messages": [response]}

def call_tools(state):
    tool_results = execute_tools(state["messages"][-1].tool_calls)
    return {"messages": tool_results}

def should_continue(state) -> str:
    if state["messages"][-1].tool_calls:
        return "tools"
    return END

builder = StateGraph(AgentState)
builder.add_node("llm", call_llm)
builder.add_node("tools", call_tools)
builder.add_edge(START, "llm")
builder.add_conditional_edges("llm", should_continue, {"tools": "tools", END: END})
builder.add_edge("tools", "llm")  # Loop back

graph = builder.compile()
```

### Checkpointing + Human-in-the-Loop
```python
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command

checkpointer = MemorySaver()
graph = builder.compile(checkpointer=checkpointer, interrupt_before=["dangerous_action"])
config = {"configurable": {"thread_id": "user-123"}}

# Pauses before "dangerous_action" node
result = graph.invoke({"messages": [("user", "Delete everything")]}, config)

# Resume after human approval
result = graph.invoke(None, config)  # None = resume from checkpoint

# Dynamic interrupt inside a node:
def my_node(state):
    user_response = interrupt("Do you approve?")  # Pauses here
    if user_response == "yes":
        return {"messages": [("assistant", "Approved!")]}
```

### Multi-Agent via Command
```python
from langgraph.types import Command

def supervisor(state):
    decision = llm.invoke("Route to: researcher or writer?")
    return Command(goto=decision, update={"messages": [("system", f"Routing to {decision}")]})

# Tool-based handoff
@tool
def transfer_to_sales(reason: str) -> Command:
    """Transfer to sales agent."""
    return Command(goto="sales_agent", update={"messages": [("system", f"Transferred: {reason}")]})
```

### What to Adopt
- **StateGraph** pattern for complex multi-step workflows
- **Checkpointing** for resumable, fault-tolerant execution
- **interrupt()** for human-in-the-loop approval gates
- **Command(goto=...)** for dynamic agent routing
- **Reducers** for predictable state updates

---

## 1.3 Role-Based Teams — CrewAI

**Repo:** github.com/crewaiinc/crewai
**Key insight:** Model AI workflows like a human team — agents have roles, tasks have context dependencies, crews orchestrate.

### Agent Definition
```python
from crewai import Agent

researcher = Agent(
    role="Senior Research Analyst",
    goal="Find comprehensive data on market trends",
    backstory="You are an experienced analyst with 10 years...",
    tools=[search_tool, scraper_tool],
    llm="gpt-4o",
    allow_delegation=True,   # Can delegate to other agents
    memory=True,             # Enable memory system
    max_iter=15,
)
```

### Task Context Dependencies
```python
from crewai import Task

research_task = Task(
    description="Research the latest AI trends for: {topic}",
    expected_output="Detailed report with findings",
    agent=researcher,
)

writing_task = Task(
    description="Write a blog post based on the research",
    expected_output="1000-word blog post in markdown",
    agent=writer,
    context=[research_task],  # ← Waits for research, gets output as context
)
```

### Crew Orchestration
```python
from crewai import Crew, Process

# Sequential — tasks run in listed order
crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, writing_task],
    process=Process.sequential,
    memory=True,
)

# Hierarchical — manager delegates
crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, writing_task],
    process=Process.hierarchical,
    manager_llm=ChatOpenAI(model="gpt-4o"),
)

result = crew.kickoff(inputs={"topic": "LLM Agents"})
```

### Built-in Delegation Tools
```python
# When allow_delegation=True, agents automatically get:

class DelegateWorkTool:
    """Delegate a task to a coworker."""
    def _run(self, task: str, coworker: str, context: str) -> str:
        target = find_agent_by_role(coworker)
        return target.execute_task(task=task, context=context)

class AskQuestionTool:
    """Ask a coworker a question."""
    def _run(self, question: str, coworker: str, context: str) -> str:
        target = find_agent_by_role(coworker)
        return target.execute_task(task=question, context=context)
```

### 4-Type Memory System
```python
# 1. Short-Term — session context (ChromaDB + RAG)
class ShortTermMemory:
    storage: ChromaDB
    def save(self, value, metadata, agent): ...
    def search(self, query, limit=3): ...

# 2. Long-Term — cross-session learning (SQLite)
class LongTermMemory:
    storage: SQLite3
    def save(self, task_description, result, quality_score): ...

# 3. Entity — structured knowledge (ChromaDB)
class EntityMemory:
    storage: ChromaDB
    def save(self, entity, entity_type, description): ...

# 4. Contextual — orchestration layer combining all three
class ContextualMemory:
    def build_context(self, task, context) -> str:
        # Queries all memory types, ranks by similarity + recency + importance
```

### What to Adopt
- **Role/goal/backstory** pattern for agent persona definition
- **Task context dependencies** for workflow chaining
- **DelegateWorkTool / AskQuestionTool** for inter-agent communication
- **4-type memory architecture** maps to Life Graph's memory scoping

---

# Part 2: Memory Systems

## 2.1 Memory Pipeline — Mem0

**Repo:** github.com/mem0ai/mem0
**Key insight:** Don't store raw chat. Extract atomic facts → consolidate (add/update/delete) → retrieve (vector + entity fusion).

### The Pipeline
```
User Messages → Extract Facts (LLM) → For each fact:
  → Embed fact
  → Search existing memories for similar
  → LLM decides: ADD new | UPDATE existing | SKIP (duplicate)
  → Store in vector DB with metadata
  → Extract entities → store in entity collection
```

### Core Interface
```python
class Memory:
    def add(self, messages, user_id=None, agent_id=None, metadata=None):
        """Extract and store memories from messages"""
        # 1. LLM extracts atomic facts
        facts = self._extract_facts(messages)
        
        for fact in facts:
            embedding = self.embedding_model.embed(fact)
            existing = self.vector_store.search(embedding, filters={"user_id": user_id}, limit=5)
            
            # 2. LLM decides action
            action = self._determine_action(fact, existing)
            
            if action.type == "ADD":
                self.vector_store.insert(embedding=embedding,
                    payload={"memory": fact, "user_id": user_id,
                             "created_at": now(), "updated_at": now()})
            elif action.type == "UPDATE":
                self.vector_store.update(id=action.target_id,
                    embedding=self.embedding_model.embed(action.updated_text),
                    payload={"memory": action.updated_text, "updated_at": now()})
    
    def search(self, query, user_id=None, limit=100):
        """Multi-signal retrieval: vector + entity fusion"""
        query_embedding = self.embedding_model.embed(query)
        results = self.vector_store.search(query_embedding, filters={"user_id": user_id})
        
        if hasattr(self, 'graph'):
            graph_results = self.graph.search(query, filters={"user_id": user_id})
            results = self._fuse_results(results, graph_results)
        return results
    
    def history(self, memory_id):
        """Get change history of a memory (audit trail)"""
        return self.db.get_history(memory_id)
```

### Entity Graph Memory
```python
class MemoryGraph:
    def add(self, messages, filters=None):
        """Extract entities + relationships, store in vector collection"""
        entities = self._extract_entities(messages)  # LLM extraction
        for entity in entities:
            existing = self.vector_store.search(embed(entity.name), collection="entities")
            if self._is_same_entity(entity, existing[0]):
                self._merge_entity(existing[0], entity)  # Merge relationships
            else:
                self.vector_store.insert(collection="entities",
                    payload={"name": entity.name, "type": entity.type, "relations": entity.relations})
    
    def search(self, query, filters=None):
        """Find entities → find linked memories (multi-hop recall)"""
        entities = self.vector_store.search(embed(query), collection="entities")
        related = []
        for entity in entities:
            memories = self.vector_store.search_by_metadata(
                filters={"entities": {"$contains": entity["name"]}})
            related.extend(memories)
        return related
```

> **⚠️ Important:** Mem0 recently REMOVED Apache AGE/Neo4j support in favor of native entity storage in the vector store. For Life Graph (which uses PostgreSQL + Apache AGE), you'll need to build your own graph storage layer or use an older Mem0 version.

### What to Adopt
- **Extract → Consolidate → Retrieve** pipeline (core pattern)
- **Scoping** by user_id, agent_id, run_id (multi-tenant memory)
- **Deduplication** via LLM comparison (avoids redundant facts)
- **Entity extraction** + multi-hop recall for relationship queries
- **Change history** for memory audit trail

---

## 2.2 OS-Inspired Memory — Letta (MemGPT)

**Repo:** github.com/letta-ai/letta
**Key insight:** Treat the LLM context window like RAM. Agent manages its own memory — swapping data between in-context (RAM) and database (disk).

### Memory Hierarchy
```
┌─────────────────────────────────────────┐
│ LLM Context Window ("RAM")               │
│  ├── System Prompt (always)              │
│  ├── Memory Blocks (agent self-edits)    │
│  │   ├── persona block                   │
│  │   └── human block                     │
│  ├── Recent Messages                     │
│  └── Available Functions                 │
└────────────────┬────────────────────────┘
                 ↕ agent calls memory tools
┌────────────────┴────────────────────────┐
│ Recall Memory ("Main Memory")            │
│  └── Full conversation log in DB         │
│      Searchable via conversation_search  │
└────────────────┬────────────────────────┘
                 ↕ agent calls archival tools
┌────────────────┴────────────────────────┐
│ Archival Memory ("Disk")                 │
│  └── Unlimited, semantic similarity      │
│      PostgreSQL + pgvector               │
└─────────────────────────────────────────┘
```

### Memory Blocks (The Core Innovation)
```python
class Block(BaseModel):
    id: str
    label: str           # e.g., "persona", "human"
    description: str     # What this block is for
    value: str           # The content — agent can READ and WRITE this
    limit: int           # Max characters (context budget)

class ChatMemory(BasicBlockMemory):
    def __init__(self, persona: str, human: str):
        super().__init__(blocks=[
            Block(label="persona", value=persona),  # Agent's identity
            Block(label="human", value=human),       # User info
        ])
```

### Built-in Self-Editing Memory Tools
```python
# Every Letta agent has these tools — it decides when to use them:

def core_memory_append(self, label: str, content: str):
    """Append to a core memory block."""
    block = self.memory.get_block(label)
    block.value += content

def core_memory_replace(self, label: str, old_content: str, new_content: str):
    """Replace content in a memory block (for corrections)."""
    block = self.memory.get_block(label)
    block.value = block.value.replace(old_content, new_content)

def conversation_search(self, query: str, page: int = 0):
    """Search past message history (recall memory)."""
    return self.recall_storage.search(query, page=page)

def archival_memory_insert(self, content: str):
    """Store in long-term archival storage."""
    self.archival_storage.insert(content)

def archival_memory_search(self, query: str, page: int = 0):
    """Search archival memory using semantic similarity."""
    return self.archival_storage.search(query, page=page)

def send_message(self, message: str):
    """Send visible message to user (terminal action)."""
    return message
```

### The Agent Loop (Heartbeat System)
```python
class Agent:
    def step(self, user_message):
        context = self._compile_context()  # system + blocks + messages + tools
        
        while True:  # Heartbeat loop
            response = self.llm.chat_completion(messages=context, functions=self.available_functions)
            
            if response.function_call.name == "send_message":
                return response.function_call.args["message"]  # Terminal
            else:
                result = self._execute_function(response.function_call)
                context.append(ToolMessage(result))
                # Continue loop — agent can chain multiple actions
```

### What to Adopt
- **Memory blocks** that agents self-edit (persona/human/custom blocks)
- **Three-tier hierarchy** (context → recall → archival)
- **Agent-controlled memory** — the agent decides what to remember/forget
- **Heartbeat loop** — agent can chain multiple actions before responding
- **PostgreSQL + pgvector** backend (matches your stack)

---

# Part 3: Tool & Output Systems

## 3.1 Type-Safe Agents — PydanticAI

**Repo:** github.com/pydantic/pydantic-ai
**Key insight:** Generic agents with dependency injection and validated structured outputs.

### Agent with Typed Output
```python
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext

class TaskPlan(BaseModel):
    title: str
    steps: list[str]
    estimated_hours: float
    priority: Literal["low", "medium", "high"]

@dataclass
class MyDeps:
    db: AsyncConnection
    user_id: str

agent = Agent(
    'openai:gpt-4o',
    output_type=TaskPlan,      # ← Guaranteed valid TaskPlan output
    deps_type=MyDeps,          # ← Type-safe dependency injection
)

# Tool with context (gets deps via RunContext)
@agent.tool
async def get_user_history(ctx: RunContext[MyDeps], limit: int) -> str:
    """Get user's past tasks."""
    rows = await ctx.deps.db.fetch(
        "SELECT * FROM tasks WHERE user_id = $1 LIMIT $2",
        ctx.deps.user_id, limit
    )
    return json.dumps(rows)

# Execution
result = agent.run_sync("Plan the WhatsApp integration", deps=MyDeps(db=conn, user_id="race"))
print(result.output.steps)  # Always valid TaskPlan
```

### Auto-Retry on Validation Failure
```python
# If LLM returns invalid output, PydanticAI automatically:
# 1. Catches ValidationError
# 2. Sends the error message back to the LLM
# 3. LLM corrects and re-generates
# 4. Up to `retries` times (default: 1)

agent = Agent('openai:gpt-4o', output_type=TaskPlan, retries=3)
```

### Agent Delegation
```python
research_agent = Agent('openai:gpt-4o', output_type=ResearchResult)
writing_agent = Agent('openai:gpt-4o', deps_type=MyDeps)

@writing_agent.tool
async def do_research(ctx: RunContext[MyDeps], topic: str) -> str:
    """Delegate research to specialist."""
    result = await research_agent.run(f"Research: {topic}", usage=ctx.usage)
    return result.output.summary  # Typed access!
```

### What to Adopt
- **Generic Agent[DepsT, OutputT]** for type safety
- **Dependency injection via RunContext** for database, config access
- **Structured output validation** with auto-retry
- **Agent delegation** as tool calls with shared usage tracking

---

## 3.2 Code-as-Action — Smolagents

**Repo:** github.com/huggingface/smolagents (~1,000 LOC core)
**Key insight:** Instead of JSON tool calls, the agent writes Python code. Tools are injected as callable functions in the execution scope.

### Two Agent Types
```python
# CodeAgent — writes Python, executes in sandbox
class CodeAgent(MultiStepAgent):
    # LLM generates:
    #   results = search_web(query="pgvector benchmarks")
    #   filtered = [r for r in results if "2025" in r]
    #   final_answer(filtered)
    # Framework parses AST → executes node-by-node → tools are in scope

# ToolCallingAgent — classic JSON function calling
class ToolCallingAgent(MultiStepAgent):
    # LLM generates: {"tool": "search_web", "args": {"query": "..."}}
```

### Tool Registration
```python
# Decorator (simple)
@tool
def search_web(query: str) -> str:
    """Searches the web. Args: query: The search query."""
    return requests.get(f"https://api.search.com?q={query}").text

# Subclass (stateful)
class DatabaseTool(Tool):
    name = "query_database"
    description = "Queries PostgreSQL."
    inputs = {"sql": {"type": "string", "description": "SQL query"}}
    output_type = "string"
    
    def __init__(self, conn_string):
        super().__init__()
        self.conn = psycopg2.connect(conn_string)
    
    def forward(self, sql: str) -> str:
        return json.dumps(self.conn.execute(sql).fetchall())
```

### Manager-Worker Multi-Agent
```python
web_agent = CodeAgent(tools=[search_web], model=model, name="web_researcher",
    description="Searches the web and extracts information")

code_agent = CodeAgent(tools=[run_python], model=model, name="code_executor",
    description="Writes and runs Python for data analysis")

# Manager has no direct tools — orchestrates via sub-agents
manager = CodeAgent(tools=[], model=model, managed_agents=[web_agent, code_agent])
# Manager generates: result = web_researcher("find X about Y")
```

### Step-Based Memory
```python
class AgentMemory:
    steps: List[Union[SystemPromptStep, TaskStep, ActionStep, PlanningStep]]

class ActionStep:
    step_number: int
    thought: str         # LLM reasoning
    tool_calls: list     # What was invoked
    observations: str    # Results
    error: str           # Errors (enables self-correction)
```

### What to Adopt
- **Code-as-action** for complex data processing (NL queries, report generation)
- **AST-based sandbox** for safe code execution
- **Step-based memory** for structured agent history logging
- **Manager-worker** pattern with managed_agents

---

## 3.3 Programming LLMs — DSPy

**Repo:** github.com/stanfordnlp/dspy
**Key insight:** Define WHAT the LLM should do (signatures), not HOW to prompt it. Auto-optimize prompts with BootstrapFewShot.

### Signatures — Declarative Task Contracts
```python
import dspy

# Quick: string-based
predictor = dspy.Predict("question -> answer")

# Rich: class-based (Pydantic-powered)
class ExtractMemory(dspy.Signature):
    """Extract structured memory from conversation."""
    conversation = dspy.InputField(desc="Raw conversation text")
    entities = dspy.OutputField(desc="Extracted entities with types")
    relationships = dspy.OutputField(desc="Relationships between entities")
    importance_score = dspy.OutputField(desc="0-1 importance score")
```

### Composable Modules (like PyTorch)
```python
class RAGPipeline(dspy.Module):
    def __init__(self):
        self.retrieve = dspy.Retrieve(k=3)
        self.reason = dspy.ChainOfThought("context, question -> answer")
    
    def forward(self, question):
        context = self.retrieve(question).passages
        return self.reason(context=context, question=question)
```

### ReAct Agent
```python
class ReAct(dspy.Module):
    def __init__(self, signature, tools, max_iters=20):
        self.tools = {t.name: t for t in tools}
    
    def forward(self, **kwargs):
        trajectory = []
        for i in range(self.max_iters):
            result = self.react_predictor(trajectory=trajectory)
            
            if result.next_tool_name == "finish":
                return result
            
            tool = self.tools[result.next_tool_name]
            observation = tool(**result.next_tool_args)
            trajectory.append({"thought": result.next_thought,
                "action": result.next_tool_name, "observation": observation})
```

### BootstrapFewShot — Auto Prompt Optimization (KILLER FEATURE)
```python
def accuracy_metric(example, pred, trace=None):
    return set(pred.entities) == set(example.entities)

optimizer = dspy.BootstrapFewShot(
    metric=accuracy_metric,
    max_bootstrapped_demos=4,
    max_labeled_demos=8
)

# Auto-finds best few-shot examples from training data
optimized = optimizer.compile(student=MemoryExtractor(), trainset=train_data)
optimized.save("optimized_extractor.json")  # Serializable!
```

### What to Adopt
- **Signatures** for declarative task contracts (memory extraction, SQL generation)
- **BootstrapFewShot** to auto-optimize prompts for your eval harness
- **ChainOfThought** as a drop-in upgrade for any Predict module
- **Module composition** for building complex pipelines from simple blocks
- **Serializable programs** — save/load optimized prompt configurations

---

# Part 4: Design Patterns Catalog

## From Microsoft AI Agents for Beginners (10 Lessons)

| # | Pattern | Description | When to Use |
|:--|:--------|:-----------|:------------|
| 1 | **Tool Use** | LLM generates function calls to trigger external APIs | Any agent that interacts with external systems |
| 2 | **Agentic RAG** | Retrieval as a tool — agent decides when to search, evaluates quality, iterates | Knowledge base queries, document Q&A |
| 3 | **Planning** | Break complex tasks into sub-steps, execute sequentially, re-plan on new observations | Multi-step code generation, research tasks |
| 4 | **Multi-Agent** | Specialized agents coordinate — manager routes, workers execute | Your agent team (Chief + specialists) |
| 5 | **Reflection** | Agent reviews its own output, detects errors, self-corrects | Code review (Sage), quality checks |
| 6 | **Metacognition** | Agent monitors its own reasoning process, explains decisions | Debugging, audit trails |
| 7 | **HITL** | Pause for human approval at high-stakes decision points | Deployments, payments, data deletion |
| 8 | **Guardrails** | Input/output validation, blocked actions, safety checks | NL queries (block mutations), tool limits |
| 9 | **Evaluation** | Systematic testing of agent quality, regression detection | Your eval harness module |
| 10 | **Production Ops** | Deployment, monitoring, cost management, scaling | Your LLM trace viewer |

---

# Part 5: Architecture Recommendations for Life Graph

## Recommended Architecture (Synthesized)

```
┌──────────────────────────────────────────────────────┐
│                    YOUR SYSTEM                        │
│                                                       │
│  ┌─────────────┐     ┌──────────────────────────┐    │
│  │   CHIEF      │     │   MEMORY (Life Graph)     │    │
│  │  (Swarm-style│     │                           │    │
│  │   handoff)   │     │  ┌─────────────────────┐  │    │
│  └──────┬───────┘     │  │ Core Memory (Letta)  │  │    │
│         │             │  │ - persona block       │  │    │
│    ┌────┼────┐        │  │ - human block         │  │    │
│    ▼    ▼    ▼        │  │ - project blocks      │  │    │
│  CODY  REX  OPS      │  └─────────────────────┘  │    │
│  (PydanticAI          │  ┌─────────────────────┐  │    │
│   typed agents        │  │ Memory Pipeline      │  │    │
│   + tools)            │  │ (Mem0-style)         │  │    │
│                       │  │ Extract → Consolidate│  │    │
│  Each agent has:      │  │ → Retrieve           │  │    │
│  - Role/Goal/Backstory│  └─────────────────────┘  │    │
│    (CrewAI-style)     │  ┌─────────────────────┐  │    │
│  - Typed tools        │  │ Graph Memory         │  │    │
│    (PydanticAI-style) │  │ (PostgreSQL + AGE)   │  │    │
│  - Step memory        │  │ Entities + Relations  │  │    │
│    (Smolagents-style) │  └─────────────────────┘  │    │
│                       └──────────────────────────┘    │
│                                                       │
│  ┌─────────────────────────────────────────────────┐  │
│  │ EXECUTION (LangGraph-style state machine)        │  │
│  │ research → code → review → human_approve → deploy│  │
│  │ + checkpointing + resume + time-travel            │  │
│  └─────────────────────────────────────────────────┘  │
│                                                       │
│  ┌─────────────────────────────────────────────────┐  │
│  │ OPTIMIZATION (DSPy-style)                         │  │
│  │ BootstrapFewShot auto-tunes prompts               │  │
│  │ Signatures define task contracts                   │  │
│  │ Eval harness validates quality                     │  │
│  └─────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────┘
```

## What to Build (Priority Order)

| # | Component | Source Pattern | Effort |
|:--|:----------|:-------------|:-------|
| 1 | **Agent base class** (typed tools, DI) | PydanticAI Agent | 2 days |
| 2 | **Handoff router** (Chief → specialists) | Swarm handoff | 1 day |
| 3 | **Memory pipeline** (extract/consolidate/retrieve) | Mem0 pipeline | 3 days |
| 4 | **Memory blocks** (self-editing core memory) | Letta blocks | 2 days |
| 5 | **Task execution graph** (state machine) | LangGraph StateGraph | 3 days |
| 6 | **Agent personas** (role/goal/backstory) | CrewAI Agent | 1 day |
| 7 | **Step-based history** (structured logging) | Smolagents ActionStep | 1 day |
| 8 | **Prompt optimization** (auto few-shot) | DSPy BootstrapFewShot | 2 days |

**Total: ~15 days for a production-quality agent system.**

## Key Technical Decisions

| Decision | Recommendation | Rationale |
|:---------|:--------------|:----------|
| **Orchestration** | Swarm-style handoff (simple) + LangGraph state machine (complex tasks) | Start simple, add complexity when needed |
| **Memory** | Mem0 pipeline + Letta blocks + PostgreSQL/pgvector/AGE | Matches your existing stack |
| **Tool system** | PydanticAI-style typed tools with RunContext DI | Type safety prevents bugs |
| **Agent communication** | CrewAI's DelegateWorkTool pattern | Simple, well-tested |
| **Prompt management** | DSPy signatures + BootstrapFewShot | Auto-optimization reduces manual work |
| **State persistence** | PostgreSQL (not ChromaDB) | Your core decision — one database |
| **LLM routing** | LiteLLM (already in your stack) | Flash for routing, Pro for reasoning |

---

*This handbook is a living document. Update as you implement patterns and discover what works for your specific use case.*
