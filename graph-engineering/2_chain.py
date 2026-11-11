# /// script
# dependencies = ["anthropic"]
# ///
import subprocess, sys, time, glob
from anthropic import Anthropic

# ── the agent: one node ─────────────────────────────────────────────────────
client = Anthropic()
MODEL = "claude-sonnet-5-5"
def request_response(**request):                         # model interface: requests a response from the model
    return client.messages.create(model=MODEL, **request)

shell = {"name": "shell", "description": "Run a shell command in the shop folder, and get back what it printed. One command can do several things, like read several files at once.",
         "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}

def run(cmd, folder=".", who="agent"):                   # agent: its body; runs one command in folder, and returns what it printed
    print(f"  {who} $ {cmd.strip().splitlines()[0][:90]}")
    done = subprocess.run(cmd, shell=True, cwd=folder, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
    return done.stdout or f"(exit {done.returncode})"

def agent(role, request, tools=(), act=lambda call: run(call.input["cmd"]), **settings):   # agent: observe → think → act until it answers
    messages, tokens = [{"role": "user", "content": request}], 0
    while True:
        response = request_response(max_tokens=16384, system=role, tools=list(tools), messages=messages, **settings)
        tokens += response.usage.input_tokens + response.usage.output_tokens   # what this node costs, in tokens
        messages.append({"role": "assistant", "content": response.content})
        calls = [block for block in response.content if block.type == "tool_use"]
        if not calls: return "".join(block.text for block in response.content if block.type == "text"), tokens   # done: its answer
        messages.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": call.id, "content": act(call)} for call in calls]})

# ── nodes ───────────────────────────────────────────────────────────────────
REQUEST = " ".join(sys.argv[1:]) or ("Add gift wrap at £3 per item. total(basket, gift_wrap=True) adds £3 for every item, counting quantities "
    "(two mugs are two items). receipt(basket, gift_wrap=True) shows the charge on its own line, like 'Gift wrap: £6.00', just above "
    "the total, and the total includes it.")             # the feature request: from the command line, or gift wrap

PLANNER = """You are the planner in a small team that works on the shop, a small Python project. You can't run anything. You get a feature request and the code, and you write a plan for the builder: which files and functions to change, how, and which tests to add. Start with one line that sums up the plan. Be short and exact, and don't write the code."""
BUILDER = """You are the builder in a small team that works on the shop, a small Python project: you're in its folder, and you work through the shell. You get a feature request and a plan. Make the change, run the tests with python3 -m unittest, and reply with a short report of what you changed. Start with one line that sums it up."""

def code():                                              # the shop's code, as text, for a node that can't look for itself
    return "\n".join(f"# ── {name}\n{open(name).read()}" for name in sorted(glob.glob("*.py")))

def planner(request):                                    # node: a model with no tools; the request and the code in, a plan out
    return agent(PLANNER, f"Feature request: {request}\n\nThe code:\n{code()}")

def builder(request, plan):                              # node: a model with the shell; the request and the plan in, a report out
    return agent(BUILDER, f"Feature request: {request}\n\nThe plan:\n{plan}", tools=[shell], act=lambda call: run(call.input["cmd"], who="builder"))

# ── trace ───────────────────────────────────────────────────────────────────
TRACE = []                                               # trace: every node that ran, as (name, seconds, tokens)
def gist(text):                                          # trace: the first line of what a node passes on, cut short
    line = next((line.strip("#*- ") for line in text.splitlines() if line.strip("#*- ")), "")
    return line[:72] + ("…" if len(line) > 72 else "")

def node(name, work, *inputs):                           # trace: runs one node, and prints how long it took, its tokens, and what it passes on
    start = time.time()
    output, tokens = work(*inputs)
    TRACE.append((name, time.time() - start, tokens))
    print(f"● {name:<9}{TRACE[-1][1]:6.1f}s {tokens:>8,} tokens  → {len(output):,} chars: {gist(output)}")
    print("  │ " + output.strip().replace("\n", "\n  │ "))   # edge: what it passes on, in full
    return output

# ── edges ───────────────────────────────────────────────────────────────────
start = time.time()
plan = node("planner", planner, REQUEST)                 # edge: the request goes into the planner
report = node("builder", builder, REQUEST, plan)         # edge: the request and the plan go into the builder
print(f"■ done     {time.time() - start:6.1f}s {sum(tokens for _, _, tokens in TRACE):>8,} tokens  route: {' → '.join(name for name, _, _ in TRACE)}")
