# /// script
# dependencies = ["anthropic"]
# ///
import subprocess, sys, time, glob, json, os, shutil, tempfile, filecmp
from concurrent.futures import ThreadPoolExecutor
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

PLANNER = """You are the planner in a small team that works on the shop, a small Python project. You can't run anything. You get a feature request and the code, and you write a plan: which files and functions to change, how, and which tests to add. Be short and exact, and don't write the code.

Split the work into parts that builders can do at the same time, each in their own copy of the shop, without seeing each other's work until the end. Each part changes its own files: no file is in two parts, and that includes test files. Since a builder can't see the other parts' code, say in each part exactly what it provides to the others and what it can count on from them: names, arguments and return values. If the work can't be split, write one part."""
PLAN = {"type": "json_schema", "schema": {"type": "object", "additionalProperties": False, "required": ["summary", "parts"], "properties": {   # the plan's shape: a summary, and parts
    "summary": {"type": "string"}, "parts": {"type": "array", "items": {"type": "object", "additionalProperties": False,
    "required": ["files", "task"], "properties": {"files": {"type": "array", "items": {"type": "string"}}, "task": {"type": "string"}}}}}}}
BUILDER = """You are the builder in a small team that works on the shop, a small Python project: you're in its folder, and you work through the shell. You get a feature request and a plan. Make the change, run the tests with python3 -m unittest, and reply with a short report of what you changed. Start with one line that sums it up."""

def code():                                              # the shop's code, as text, for a node that can't look for itself
    return "\n".join(f"# ── {name}\n{open(name).read()}" for name in sorted(glob.glob("*.py")))

def planner(state):                                      # node: a model with no tools; reads the request, writes the plan, split into parts
    plan, tokens = agent(PLANNER, f"Feature request: {state['request']}\n\nThe code:\n{code()}", output_config={"format": PLAN})
    return {"plan": json.loads(plan)}, tokens

def builder(state):                                      # node: a model with the shell; reads the request, the plan and any failed tests, writes its report
    brief = f"Feature request: {state['request']}\n\nThe plan:\n{json.dumps(state['plan'], indent=2, ensure_ascii=False)}"
    if state.get("passed") is False: brief += f"\n\nThe tests failed after the last build. Fix them:\n{state['tests']}"
    report, tokens = agent(BUILDER, brief, tools=[shell], act=lambda call: run(call.input["cmd"], who="builder"))
    return {"report": report}, tokens

def build_part(state, number, part):                     # one builder, on its own copy of the shop, for one part of the plan
    copy, start = tempfile.mkdtemp(), time.time()
    shutil.copytree(".", copy, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".graph", "__pycache__"))
    brief = (f"Feature request: {state['request']}\n\nThe plan:\n{json.dumps(state['plan'], indent=2, ensure_ascii=False)}\n\n"
             f"You build part {number}: {part['task']}\nChange only {', '.join(part['files'])}. Other builders are building the other parts at the same time, in their own copies.")
    report, tokens = agent(BUILDER, brief, tools=[shell], act=lambda call: run(call.input["cmd"], copy, f"builder {number}"))
    changed = [f for f in os.listdir(copy) if os.path.isfile(f"{copy}/{f}") and not (os.path.isfile(f) and filecmp.cmp(f"{copy}/{f}", f, shallow=False))]
    print(f"  ● builder {number} {time.time() - start:5.1f}s {tokens:>8,} tokens  → changed {', '.join(changed) or 'nothing'}: {gist(report)}")
    return {"part": number, "files": part["files"], "changed": changed, "seconds": round(time.time() - start, 1), "report": report, "folder": copy}, tokens

def builders(state):                                     # node: fan-out; one builder per part, all at the same time, in threads
    parts = list(enumerate(state["plan"]["parts"], 1))
    with ThreadPoolExecutor() as pool: results = list(pool.map(lambda numbered: build_part(state, *numbered), parts))
    built = [part for part, _ in results]
    print(f"  {len(built)} builders at once; one after another they'd take {' + '.join(str(b['seconds']) for b in built)} = {sum(b['seconds'] for b in built):.1f}s")
    return {"built": built}, sum(tokens for _, tokens in results)

def merge(state):                                        # node: fan-in, plain code; brings each part's own files back into the shop
    merged, dropped = [], []
    for part in state["built"]:
        for f in part["changed"]:
            if f in part["files"]: shutil.copy(f"{part['folder']}/{f}", f); merged.append(f)   # its own file: kept
            else: dropped.append(f"{f} (part {part['part']})")   # someone else's file: left out
    return {"merged": merged, "dropped": dropped}, 0

def tests(state):                                        # node: plain code, no model; runs the shop's tests, writes whether they passed
    done = subprocess.run("python3 -m unittest -q", shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return {"passed": done.returncode == 0, "tests": done.stdout[-3000:]}, 0

# ── state ───────────────────────────────────────────────────────────────────
STATE = ".graph/state.json"                              # state: the shared record every node reads from and writes to, kept in a file
def save(state):                                         # state: written after every node, so it can be read at any point
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w") as f: json.dump(state, f, indent=2, ensure_ascii=False)

# ── trace ───────────────────────────────────────────────────────────────────
TRACE = []                                               # trace: every node that ran, as (name, seconds, tokens)
def gist(value):                                         # trace: the first line of what a node wrote, cut short
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    line = next((line.strip("#*-= ") for line in text.splitlines() if line.strip("#*-= ")), "")
    return line[:72] + ("…" if len(line) > 72 else "")

def node(name, state):                                   # trace: runs one node on the state, and prints how long it took, its tokens, and what it wrote
    start = time.time()
    update, tokens = NODES[name](state)
    state.update(update); state["route"].append(name); save(state)   # state: what the node wrote goes into the shared record
    TRACE.append((name, time.time() - start, tokens))
    print(f"● {name:<9}{TRACE[-1][1]:6.1f}s {tokens:>8,} tokens  → " + "; ".join(f"{key}: {gist(value)}" for key, value in update.items()))
    return update

# ── edges ───────────────────────────────────────────────────────────────────
END = "end"
NODES = {"planner": planner, "builders": builders, "merge": merge, "builder": builder, "tests": tests}   # graph: the nodes, by name
def back(state):                                         # router: back to the builder, but three builds at most
    return "builder" if state["route"].count("builder") < 3 else END
EDGES = {"planner": "builders", "builders": "merge", "merge": "tests", "builder": "tests",   # edge: where each node leads; fan-out, then fan-in
         "tests": lambda state: END if state["passed"] else back(state)}   # router: a rule: passed → end, failed → the builder again

def run_graph(request, at="planner"):                    # graph: from the first node, follow the edges to the end
    state = {"request": request, "route": []}            # state: it starts with the request
    while at != END:
        node(at, state)
        if not callable(EDGES[at]): at = EDGES[at]       # edge: a fixed edge, always taken
        else: at = EDGES[at](state); print(f"  ⑂ router → {at}")   # router: a rule reads the state and picks the next node
    return state

start = time.time()
state = run_graph(REQUEST)
print(f"■ done     {time.time() - start:6.1f}s {sum(tokens for _, _, tokens in TRACE):>8,} tokens  route: {' → '.join(state['route'])}")
