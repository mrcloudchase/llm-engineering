# Graph Engineering

By **[Chase Dovey](https://cdovey.dev/)** · [Average Joes Lab](https://github.com/averagejoeslab)

*The purpose of this module is to teach Graph Engineering*

Graph engineering is the practice of designing how agents and steps connect. To do it, you first need to know what a graph of agents is and what it's made of. Then we'll build a graph piece by piece using a simple task as guidance, evaluate it against one agent working alone, and get it ready for production.

## What is a graph of agents?

A graph of agents is a system where the work is split into steps, some of them agents, each doing one part of the job. Each step passes its results along, and something decides which step runs next.

You've seen one work. Imagine you're cooking alone in a restaurant kitchen on a Friday night.

**Alone:** tickets pile up. You read one, cook it, plate it, taste it, and send it out. It tastes right to you: you made it. Table four asked for no nuts, three tickets ago, and you've forgotten. Every dish waits for you, one pan at a time.

**A brigade:** now the kitchen has stations. The grill only grills, the sauce station only makes sauce, pastry only makes desserts.  
**Tickets** carry each order from station to station, with what the next station needs to know: *two steaks, medium, no nuts*.  
**The rail** above the pass holds every ticket, so anyone can see where each order is up to.  
**Someone calls the orders.** They read the rail and decide what happens next: *grill, fire table six. Sauce, that's not right, send it back.*

The steak and the dessert for one table are made at the same time, by different people. A plate is checked by someone who didn't cook it. Nobody has to remember everything.

```
                    someone calling the orders
                 "grill: fire six. sauce: redo it"
             ┌─────────────────┬─────────────────┐
             ▼                 ▼                 ▼
           grill ──ticket──► sauce ──ticket──► pass ─► table
             │                 │                 │
             └────────────► the rail ◄───────────┘
                   every ticket, and where it's up to
```

In short: stations do the work, tickets carry it between them, the rail holds what they share, and someone decides what's next.

### Start from the agent, now one node

An agent is a model inside a harness, looping over three steps: it observes, thinks, and acts. The model does the thinking: tokens (pieces of text) go in, and it predicts the tokens that come next. The harness does the rest: it shows the model the request, runs the commands the model asks for, sends back what they printed, and goes again until the model answers without asking for anything. One run takes a request and returns a result. (To build one from first principles, see [harness engineering](../harness-engineering/).)

In this module, one agent run is one box: a request goes in, a result comes out. In a graph, that box is a **node**, one station in the kitchen:

```
             ┌─────────────────── agent ────────────────────┐
request ───► │ model + harness: observe → think → act, loop │ ───► result
             └──────────────────────────────────────────────┘
```

A node doesn't have to hold a model. "Run the tests" is a node too: plain code, no model, the same answer every time, and free. Deciding which work needs a model and which is plain code is a large part of graph engineering.

### What one agent can't do well

One agent can do a lot. But as the work grows, three things get in its way:

| What gets in the way | Why | In the kitchen |
|---|---|---|
| **Its window fills** | everything it read and did stays in its context, what it's shown on every call, so the request competes with all of it | forgetting table four's note |
| **It grades its own work** | the one who built it checks it, with the same reading of the request, often with tests it wrote itself | tasting your own sauce |
| **Nothing runs in parallel** | one loop does one thing at a time | one cook, one pan |

A graph costs something too: more model calls, more tokens, more pieces to go wrong. On a small task, one agent can be cheaper and just as good. So we'll keep one agent as the baseline, and every node we add has to earn its place against it.

### A graph makes the structure explicit

Inside one agent, the structure of the work (plan it, build it, check it) is implicit: it's whatever the model happens to do next. A graph writes that structure down, outside the model, where you can see it, test it and change it: which units of work there are, what passes between them, what they share, and what decides what runs next.

```
       ┌──────────────────────────── state ──────────────────────────────┐
       │        what every node can read, and what each one wrote        │
       └─────────────────────────────────────────────────────────────────┘
request ─► node ──edge──► node ──edge──► router ─⑂─► node ─► … ─► result
                                                 └─► node
```

## Graph Primitives

In the kitchen, they were the stations, the tickets, the rail, and the person calling the orders. A graph of agents can be reduced to the same four primitives:

| Primitive | What it does |
|---|---|
| **Node** | a unit of work (e.g. an agent, a tool, plain code, a check) |
| **Edge** | what passes from one node to the next, and when (e.g. a plan, a diff, a test result) |
| **State** | what the nodes share (e.g. the request, the plan, whether the tests passed) |
| **Router** | what picks the next node (e.g. a fixed edge, a rule, a model) |

**Node:** a unit of work, with an input and an output. An agent is a node: a request in, a report out. So is a function that runs the tests, or one that copies files. A node can hold a model, a model with tools, or no model at all.

**Edge:** a connection from one node to the next. It says *what* passes (the plan, the diff) and *when* (always, or only if the tests passed). An edge is also a choice about what the next node gets to see, and so what it doesn't.

**State:** the record the nodes share. Instead of every node handing everything to the next, each one reads what it needs from the state, and writes back what it did. It's also where you look to see what happened, and where a run can pick up after a crash.

**Router:** the part that picks the next node. It can be fixed (the builder always follows the planner), a rule (if the tests failed, go back to the builder), or a model (an orchestrator that reads the state and decides).

Every multi-agent system is these four, in some arrangement. So let's build one.

## Building a Graph

Building a graph starts with the work: what has to be done, which parts depend on each other, and which can be checked. We'll use the same agent as every node that needs a model: Claude Sonnet, through Anthropic's Python SDK, with one tool, the shell. What changes from node to node is its role, what it's given, and what it may do.

We'll build the graph one primitive at a time, giving every version the same task to guide us, and seeing what each piece buys and what it costs.

**The task:** [`shop/`](./shop/) is a tiny Python project. `prices.py` works out what a basket costs, `receipt.py` prints the receipt, and `test_shop.py` tests them. A basket is a list of `(name, price, quantity)` lines. The feature request we'll carry through every step:

> Add gift wrap at £3 per item. total(basket, gift_wrap=True) adds £3 for every item, counting quantities (two mugs are two items). receipt(basket, gift_wrap=True) shows the charge on its own line, like 'Gift wrap: £6.00', just above the total, and the total includes it.

It touches two files, so later it can be split between two builders.

How do we know it was done right? Not from what anyone says. [`acceptance.py`](./acceptance.py) holds this request and three others, each with **hidden acceptance tests**: checks with known right answers. No node is ever given them, and in the evaluation they aren't even in the folder the nodes work in. We run them after the work is done, on what was built.

We'll build outward from one agent: first split it in two, then give the pieces a shared record, let a rule choose the path, run work in parallel, let a reviewer send work back, and finally let a model draw the graph.

### Setup

You need [uv](https://docs.astral.sh/uv/) to run the code and an [Anthropic API key](https://console.anthropic.com/). In your clone of this repo, move into the task's folder and give it your key. Every command from here on runs in `shop/`:

```bash
cd graph-engineering/shop
export ANTHROPIC_API_KEY=your-key
```

**The builder nodes run shell commands on your machine, without asking you.** They're told to work in the shop folder, and until production nothing makes them. Run this somewhere that's fine: a container, or a machine you don't mind.

The graph changes the shop's files as it goes. `git checkout . && git clean -fd` puts them back. Each graph also keeps its state in `shop/.graph/`, which git ignores.

Here are the hidden checks for gift wrap, run on the shop as it is:

```bash
uv run ../acceptance.py gift_wrap
```

```
FAIL  total([('mug', 8.5, 2), ('card', 2.0, 1)], gift_wrap=True) == 28.0
PASS  total([('mug', 8.5, 2), ('card', 2.0, 1)]) == 19.0
FAIL  receipt([('mug', 8.5, 2), ('card', 2.0, 1)], gift_wrap=True).splitlines()[-2] == 'Gift wrap: £9.00'
FAIL  receipt([('mug', 8.5, 2), ('card', 2.0, 1)], gift_wrap=True).splitlines()[-1] == 'Total: £28.00'
PASS  'Gift wrap' not in receipt([('mug', 8.5, 2), ('card', 2.0, 1)])
PASS  the shop's own tests pass
gift_wrap: 3/6 checks passed
```

The three that pass only check that nothing broke. The other three need gift wrap.

### 1. One agent does it all: the baseline

We start with one node: an agent that plans, builds and judges its own work. Every later step uses this same agent inside its nodes, so here it is once, in full.

```
                ┌──────────────────── agent ─────────────────────┐
request ──────► │  plans it, builds it, and judges its own work  │ ──────► "done"
                └────────────────────────────────────────────────┘
```

`agent()` is the loop. It sends the conversation to the model and adds the reply. If the reply asks for commands, `act()` carries out each one and the results go back; when the model answers without asking for anything, that answer is what the node passes on. It returns the answer and the tokens it used, so we can count what each node costs. `role` is its system prompt: who this node is. `run()` is its body: one shell command, in a folder. `settings` passes anything else to the model; we'll use it later to ask for answers in a fixed shape.

In [`1_one_agent.py`](./1_one_agent.py):

```python
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

# ── one agent does it all ───────────────────────────────────────────────────
REQUEST = " ".join(sys.argv[1:]) or ("Add gift wrap at £3 per item. total(basket, gift_wrap=True) adds £3 for every item, counting quantities "
    "(two mugs are two items). receipt(basket, gift_wrap=True) shows the charge on its own line, like 'Gift wrap: £6.00', just above "
    "the total, and the total includes it.")             # the feature request: from the command line, or gift wrap

ENGINEER = """You are a software engineer. You're in the folder of the shop, a small Python project, and you work through the shell. Plan the change you're asked for, make it, and check your work. Then reply with a short report: what you changed, and whether the request is done."""

start = time.time()
answer, tokens = agent(ENGINEER, REQUEST, tools=[shell])   # one node: plans, builds and judges its own work
print(f"● agent    {time.time() - start:6.1f}s {tokens:>8,} tokens")
print("> " + answer.replace("\n", "\n  "))
print(f"■ done     {time.time() - start:6.1f}s {tokens:>8,} tokens")
```

We run it:

```bash
uv run ../1_one_agent.py
```

From here on, `$` is a command a node ran (its first line, cut short), `●` is a node that finished, with how long it took and how many tokens it used, `>` is what the agent said, and `■` is the whole run.

```
  agent $ cd . && ls -R | grep -v pyc | head -50 && cat *.py | head -300
  agent $ python - <<'E'
● agent       7.5s    4,812 tokens
> Gift wrap is added and the tests pass.
  
  - **`prices.py`:** I added `GIFT_WRAP_PRICE = 3.00` and a `gift_wrap_charge(basket)` function that charges £3 per item, counting quantities. `total(basket, gift_wrap=False)` now adds that charge when `gift_wrap=True`.
  - **`receipt.py`:** `receipt(basket, gift_wrap=False)` now puts a `Gift wrap: £X.XX` line just above the total when `gift_wrap=True`. The total includes the charge.
  - **`test_shop.py`:** I added two tests using the existing basket (3 items, so £9 of wrap and a £28 total). One covers `total` and one covers `receipt`.
  
  Existing calls without `gift_wrap` behave as before.
■ done        7.5s    4,812 tokens
```

It says it's done and the tests pass. Its first command read every file; its second was a Python script, of which the trace shows only the first line. Now we check what it built, with the checks it was never given:

```bash
uv run ../acceptance.py gift_wrap
```

```
PASS  total([('mug', 8.5, 2), ('card', 2.0, 1)], gift_wrap=True) == 28.0
PASS  total([('mug', 8.5, 2), ('card', 2.0, 1)]) == 19.0
PASS  receipt([('mug', 8.5, 2), ('card', 2.0, 1)], gift_wrap=True).splitlines()[-2] == 'Gift wrap: £9.00'
PASS  receipt([('mug', 8.5, 2), ('card', 2.0, 1)], gift_wrap=True).splitlines()[-1] == 'Total: £28.00'
PASS  'Gift wrap' not in receipt([('mug', 8.5, 2), ('card', 2.0, 1)])
PASS  the shop's own tests pass
gift_wrap: 6/6 checks passed
```

Its claim holds: 6 of 6. Three model calls, 7.5 seconds and 4,812 tokens. That's the bar every graph in this module has to clear.

But we only know it holds because we checked. The same mind planned the change, wrote the code, wrote the tests that check the code, and decided it was done. Nothing in it is separate, so nothing can be checked, swapped or run at the same time. Splitting it starts with two nodes and an edge between them.

### 2. Chain: plan → build

The first two primitives are the **node** and the **edge**. We split the agent into two nodes with different roles. The **planner** has no tools: it reads the request and the code, and writes a plan. The **builder** has the shell: it reads the request and the plan, and makes the change. The **edge** between them carries the plan.

```
request ─► planner ──── plan ────► builder ─► report
           no tools,               the shell
           writes a plan           makes the change
```

The planner can't look at the code itself, so `code()` reads the shop's files and puts them in its request: a node with no tools gets what it needs through its input. `node()` runs a node, and prints its trace line and what it passes on.

In [`2_chain.py`](./2_chain.py), the agent section is the same, and this is added:

```python
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
```

Put the shop back with `git checkout . && git clean -fd`, then run it:

```bash
uv run ../2_chain.py
```

Lines after `│` are what a node passed on, in full, and the `■` line now ends with the route: the nodes in the order they ran.

```
● planner     9.5s    2,213 tokens  → 2,096 chars: Plan: add a `gift_wrap_charge` helper in `prices.py`, give `total` and `…
  │ **Plan: add a `gift_wrap_charge` helper in `prices.py`, give `total` and `receipt` an optional `gift_wrap=False` argument, and add a "Gift wrap" line to the receipt just above the total.**
  │ 
  │ **prices.py**
  │ - Add the constant `GIFT_WRAP_PRICE = 3.00`.
  │ - Add `gift_wrap_charge(basket)`. It returns `round(GIFT_WRAP_PRICE * sum(quantity for _, _, quantity in basket), 2)`, so quantities count (two mugs are two items).
  │ - Change `total(basket)` to `total(basket, gift_wrap=False)`. If `gift_wrap` is true, return `round(subtotal(basket) + gift_wrap_charge(basket), 2)`. Otherwise return `subtotal(basket)` as now.
  │ - Leave `subtotal` alone. It stays the goods-only figure.
  │ 
  │ **receipt.py**
  │ - Import `gift_wrap_charge` along with `total`.
  │ - Change `receipt(basket)` to `receipt(basket, gift_wrap=False)`.
  │ - After building the item lines, if `gift_wrap` is true, append `f"Gift wrap: £{gift_wrap_charge(basket):.2f}"`. This must come before the Total line.
  │ - Build the Total line with `total(basket, gift_wrap=gift_wrap)`, so it includes the charge.
  │ - With `gift_wrap=False`, the output must be identical to today's.
  │ - For an empty basket with `gift_wrap=True`, the line reads `Gift wrap: £0.00`. This is acceptable, so don't special-case it.
  │ 
  │ **test_shop.py** (keep the three existing tests unchanged, since they cover the default behaviour). Add:
  │ - `test_gift_wrap_charge`: `gift_wrap_charge(BASKET) == 9.0`, because BASKET has 3 items.
  │ - `test_gift_wrap_charge_counts_quantity`: `gift_wrap_charge([("mug", 8.5, 2)]) == 6.0`.
  │ - `test_total_with_gift_wrap`: `total(BASKET, gift_wrap=True) == 28.0`.
  │ - `test_total_gift_wrap_false_explicit`: `total(BASKET, gift_wrap=False) == 19.0`.
  │ - `test_receipt_with_gift_wrap`: `receipt(BASKET, gift_wrap=True) == "2 x mug: £17.00\n1 x card: £2.00\nGift wrap: £9.00\nTotal: £28.00"`.
  │ - `test_receipt_gift_wrap_single_line`: `receipt([("mug", 8.5, 2)], gift_wrap=True)` contains the line `Gift wrap: £6.00` immediately before `Total: £23.00`. This matches the example in the request.
  │ 
  │ Update the `from prices import ...` line in the tests to include `gift_wrap_charge`.
  builder $ cat prices.py receipt.py test_shop.py; ls
  builder $ python3 - <<'EOF'
● builder     9.2s    8,487 tokens  → 709 chars: I added gift wrap at £3 per item, counting quantities, and all 9 tests p…
  │ I added gift wrap at £3 per item, counting quantities, and all 9 tests pass: the 3 existing ones and 6 new ones.
  │ 
  │ - **`prices.py`:** I added `GIFT_WRAP_PRICE = 3.00` and `gift_wrap_charge(basket)`. `total(basket, gift_wrap=False)` now adds the charge when `gift_wrap` is true. `subtotal` is unchanged.
  │ - **`receipt.py`:** `receipt(basket, gift_wrap=False)` adds a `Gift wrap: £X.XX` line just above the total, and the total includes the charge. With `gift_wrap=False` the output is the same as before.
  │ - **`test_shop.py`:** I added the six tests from the plan and put `gift_wrap_charge` in the import line. The single-mug receipt test checks that `Gift wrap: £6.00` is immediately followed by `Total: £23.00`.
■ done       18.7s   10,700 tokens  route: planner → builder
```

The plan travelled along the edge, and the builder followed it: the same names, the same tests. It passes the hidden checks too (6/6). It took 18.7 seconds and 10,700 tokens, against the single agent's 7.5 seconds and 4,812: two nodes did the same work, and the builder still read every file itself.

Every node gets what it needs as arguments: the builder needs the request *and* the plan. As the graph grows, each node would need more arguments, threaded through every call, and nothing keeps a record: when the run ends, the plan is gone. Next is a record every node shares: state.

### 3. State: a shared record

Next is **state**: a record every node reads from and writes to. Instead of handing everything to the next node, each node reads what it needs from the state and returns only what it wrote; the graph merges that in and saves it to a file after every node. The edges now say only where to go next.

```
     ┌──────────────────── state: .graph/state.json ────────────────────┐
     │   request         plan           report          route           │
     └────▲─────────┬──────▲─────────┬──────▲───────────────────────────┘
          │         ▼      │         ▼      │
request ──┘      planner ──┴──────► builder ┴────► end
```

The graph itself becomes data: `NODES` names each node, `EDGES` says where each one leads, and `run_graph()` starts at the planner and follows the edges until it reaches the end.

In [`3_state.py`](./3_state.py), the nodes now take the state and return what they wrote:

```python
def planner(state):                                      # node: a model with no tools; reads the request, writes the plan
    plan, tokens = agent(PLANNER, f"Feature request: {state['request']}\n\nThe code:\n{code()}")
    return {"plan": plan}, tokens

def builder(state):                                      # node: a model with the shell; reads the request and the plan, writes its report
    report, tokens = agent(BUILDER, f"Feature request: {state['request']}\n\nThe plan:\n{state['plan']}", tools=[shell], act=lambda call: run(call.input["cmd"], who="builder"))
    return {"report": report}, tokens
```

and `save()`, `node()` and the edges are added:

```python
# ── state ───────────────────────────────────────────────────────────────────
STATE = ".graph/state.json"                              # state: the shared record every node reads from and writes to, kept in a file
def save(state):                                         # state: written after every node, so it can be read at any point
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w") as f: json.dump(state, f, indent=2, ensure_ascii=False)
```

```python
def node(name, state):                                   # trace: runs one node on the state, and prints how long it took, its tokens, and what it wrote
    start = time.time()
    update, tokens = NODES[name](state)
    state.update(update); state["route"].append(name); save(state)   # state: what the node wrote goes into the shared record
    TRACE.append((name, time.time() - start, tokens))
    print(f"● {name:<9}{TRACE[-1][1]:6.1f}s {tokens:>8,} tokens  → " + "; ".join(f"{key}: {gist(value)}" for key, value in update.items()))
    return update

# ── edges ───────────────────────────────────────────────────────────────────
END = "end"
NODES = {"planner": planner, "builder": builder}         # graph: the nodes, by name
EDGES = {"planner": "builder", "builder": END}           # edge: where each node leads

def run_graph(request, at="planner"):                    # graph: from the first node, follow the edges to the end
    state = {"request": request, "route": []}            # state: it starts with the request
    while at != END:
        node(at, state)
        at = EDGES[at]
    return state

start = time.time()
state = run_graph(REQUEST)
print(f"■ done     {time.time() - start:6.1f}s {sum(tokens for _, _, tokens in TRACE):>8,} tokens  route: {' → '.join(state['route'])}")
```

Put the shop back, then run it:

```bash
uv run ../3_state.py
```

```
● planner     9.4s    2,172 tokens  → plan: Plan: add a `gift_wrap_charge` helper in `prices.py`, give `total` and `…
  builder $ ls; cat prices.py receipt.py test_shop.py
  builder $ python3 - <<'EOF'
● builder    11.7s    8,421 tokens  → report: Gift wrap at £3 per item is in, and all 9 tests pass (the 3 existing one…
■ done       21.1s   10,593 tokens  route: planner → builder
```

Every node's work is now in one place, as it happened:

```bash
cat .graph/state.json
```

```
{
  "request": "Add gift wrap at £3 per item. total(basket, gift_wrap=True) adds £3 for every item, counting quantities (two mugs are two items). receipt(basket, gift_wrap=True) shows the charge on its own line, like 'Gift wrap: £6.00', just above the total, and the total includes it.",
  "route": [
    "planner",
    "builder"
  ],
  "plan": "**Plan: add a `gift_wrap_charge` helper in `prices.py`, give `total` and `receipt` an optional `gift_wrap=False` argument, and have the receipt show the charge on its own line just above the total.**\n\n**prices.py**\n- Add the constant `GIFT_WRAP_PER_ITEM = 3.00`.\n…",
  "report": "Gift wrap at £3 per item is in, and all 9 tests pass (the 3 existing ones plus 6 new ones).\n\n- **`prices.py`:**\n  - I added `GIFT_WRAP_PER_ITEM = 3.00` and `gift_wrap_charge(basket)`, which counts quantities.\n…"
}
```

(trimmed: the plan and the report are cut short)

But the graph runs the same path whatever happens. Nothing checks the build, and if the builder breaks something, the graph ends anyway. Choosing the next node from what happened is next: a router.

### 4. Router: conditional edges

Next is the **router**: what picks the next node. So far every edge was fixed. Now an edge can be a rule: a function that reads the state and returns the next node's name. We add a `tests` node with no model in it, which runs the shop's tests and writes whether they passed. After it, a rule routes: passed, go to the end; failed, go back to the builder, with the failures in the state for it to read. `back()` caps it at three builds, so a builder that can't fix it can't loop forever.

```
request ─► planner ─► builder ─► tests ─⑂─ passed ─► end
                         ▲              │
                         └── failed ────┘   (three builds at most)
```

In [`4_router.py`](./4_router.py), `tests()` is added, and the builder reads the failures when there are some:

```python
def builder(state):                                      # node: a model with the shell; reads the request, the plan and any failed tests, writes its report
    brief = f"Feature request: {state['request']}\n\nThe plan:\n{state['plan']}"
    if state.get("passed") is False: brief += f"\n\nThe tests failed after the last build. Fix them:\n{state['tests']}"
    report, tokens = agent(BUILDER, brief, tools=[shell], act=lambda call: run(call.input["cmd"], who="builder"))
    return {"report": report}, tokens

def tests(state):                                        # node: plain code, no model; runs the shop's tests, writes whether they passed
    done = subprocess.run("python3 -m unittest -q", shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return {"passed": done.returncode == 0, "tests": done.stdout[-3000:]}, 0
```

The `tests` edge becomes a rule, and `run_graph()` follows a rule by calling it:

```python
NODES = {"planner": planner, "builder": builder, "tests": tests}   # graph: the nodes, by name
def back(state):                                         # router: back to the builder, but three builds at most
    return "builder" if state["route"].count("builder") < 3 else END
EDGES = {"planner": "builder", "builder": "tests",       # edge: where each node leads
         "tests": lambda state: END if state["passed"] else back(state)}   # router: a rule: passed → end, failed → the builder again
```

```python
def run_graph(request, at="planner"):                    # graph: from the first node, follow the edges to the end
    state = {"request": request, "route": []}            # state: it starts with the request
    while at != END:
        node(at, state)
        if not callable(EDGES[at]): at = EDGES[at]       # edge: a fixed edge, always taken
        else: at = EDGES[at](state); print(f"  ⑂ router → {at}")   # router: a rule reads the state and picks the next node
    return state
```

Put the shop back, then run it. `⑂` is a router's choice:

```bash
uv run ../4_router.py
```

```
● planner     8.9s    2,034 tokens  → plan: Plan: add a `gift_wrap` option, off by default, with the £3-per-item cha…
  builder $ cat prices.py receipt.py test_shop.py; ls
  builder $ python3 - <<'EOF'
● builder    10.4s    8,110 tokens  → report: I added the optional gift wrap at £3 per item, and all 6 tests pass (the…
● tests       0.1s        0 tokens  → passed: true; tests: Ran 6 tests in 0.000s
  ⑂ router → end
■ done       19.4s   10,144 tokens  route: planner → builder → tests
```

The tests passed, so the router took the edge to the end. The rule cost nothing: no model call, 0.1 seconds. The edge back to the builder wasn't needed this time, because the builder had already run the tests itself; it's there for when the build is wrong.

Everything still runs one after another. But this request has two parts that don't need each other's code to be written: the price in `prices.py`, and the line on the receipt in `receipt.py`. Running them at the same time is next: fan-out.

### 5. Fan-out, fan-in: parallel nodes, merged

**Fan-out** is an edge to several nodes at once; **fan-in** is a node that waits for all of them and joins their work. It's built from the same primitives: the planner now splits the plan into parts, each with its own files, and asks for its answer in a fixed shape (`PLAN`) so code can read the parts. The `builders` node starts one builder per part, all at once, in threads. Each works in its own copy of the shop, so they can't step on each other's files, and none sees the others' work until the end. The `merge` node is plain code: it copies each part's own files back into the shop, and leaves out anything a builder changed that wasn't its own.

```
                       ┌► builder 1 ─┐
request ─► planner ────┼► builder 2 ─┼─► merge ─► tests ─⑂─ passed ─► end
           parts       └► …         ─┘                    │
                                           builder ◄─ failed
```

Since the builders can't see each other's code, the planner has to say what each part provides to the others: names, arguments, return values. That's the contract they build against.

In [`5_fan_out.py`](./5_fan_out.py), the planner's role grows a paragraph, and it answers in the plan's shape:

```python
PLANNER = """You are the planner in a small team that works on the shop, a small Python project. You can't run anything. You get a feature request and the code, and you write a plan: which files and functions to change, how, and which tests to add. Be short and exact, and don't write the code.

Split the work into parts that builders can do at the same time, each in their own copy of the shop, without seeing each other's work until the end. Each part changes its own files: no file is in two parts, and that includes test files. Since a builder can't see the other parts' code, say in each part exactly what it provides to the others and what it can count on from them: names, arguments and return values. If the work can't be split, write one part."""
PLAN = {"type": "json_schema", "schema": {"type": "object", "additionalProperties": False, "required": ["summary", "parts"], "properties": {   # the plan's shape: a summary, and parts
    "summary": {"type": "string"}, "parts": {"type": "array", "items": {"type": "object", "additionalProperties": False,
    "required": ["files", "task"], "properties": {"files": {"type": "array", "items": {"type": "string"}}, "task": {"type": "string"}}}}}}}
```

```python
def planner(state):                                      # node: a model with no tools; reads the request, writes the plan, split into parts
    plan, tokens = agent(PLANNER, f"Feature request: {state['request']}\n\nThe code:\n{code()}", output_config={"format": PLAN})
    return {"plan": json.loads(plan)}, tokens
```

`build_part()`, `builders()` and `merge()` are added:

```python
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
```

and the edges fan out and back in:

```python
NODES = {"planner": planner, "builders": builders, "merge": merge, "builder": builder, "tests": tests}   # graph: the nodes, by name
def back(state):                                         # router: back to the builder, but three builds at most
    return "builder" if state["route"].count("builder") < 3 else END
EDGES = {"planner": "builders", "builders": "merge", "merge": "tests", "builder": "tests",   # edge: where each node leads; fan-out, then fan-in
         "tests": lambda state: END if state["passed"] else back(state)}   # router: a rule: passed → end, failed → the builder again
```

Put the shop back, then run it:

```bash
uv run ../5_fan_out.py
```

The builders' commands interleave, because they run at the same time:

```
● planner    14.3s    2,972 tokens  → plan: {"summary": "Gift wrap is £3 per item, counting quantities. prices.py ge…
  builder 1 $ cat prices.py; ls
  builder 2 $ cat receipt.py prices.py; ls
  builder 1 $ python3 - <<'EOF'
  builder 2 $ cat > receipt.py <<'EOF'
  ● builder 1   7.0s    9,477 tokens  → changed prices.py, test_prices_gift_wrap.py: Gift wrap is now in `prices.py`, and all 9 tests pass: the existing ones…
  ● builder 2   8.3s   10,369 tokens  → changed receipt.py, test_receipt_gift_wrap.py: Part 2 is written, but the tests can't pass in my copy yet. `prices.py` …
  2 builders at once; one after another they'd take 7.0 + 8.3 = 15.3s
● builders    8.3s   19,846 tokens  → built: [{"part": 1, "files": ["prices.py", "test_prices_gift_wrap.py"], "change…
● merge       0.0s        0 tokens  → merged: ["prices.py", "test_prices_gift_wrap.py", "receipt.py", "test_receipt_gi…; dropped: []
● tests       0.0s        0 tokens  → passed: true; tests: Ran 12 tests in 0.000s
  ⑂ router → end
■ done       22.7s   22,818 tokens  route: planner → builders → merge → tests
```

The two builders took 7.0 and 8.3 seconds; at once, the fan-out took 8.3. One after another, it would have taken 15.3.

Builder 2 couldn't finish its own check: *"the tests can't pass in my copy yet"*, because its receipt calls the `gift_wrap_charge()` that builder 1 was writing in another copy. It built against the contract in the plan, and the first place the two parts met was the `tests` node after the merge. They passed, 12 tests, and so do the hidden checks (6/6). That's the price of parallel work: each part is checked alone, and only the merge shows whether they fit.

The tests passing means the code does what the tests say. But the tests were written by the same builders who wrote the code, from the same reading of the request. Nobody has checked the work against the request itself. That's next: a reviewer, and an edge back.

### 6. Cycle: review sends work back, with a limit

A **cycle** is an edge that goes back to an earlier node. We add a `reviewer` node: a different role, one that didn't write the change. It gets the request and the diff, can read the code and run things, and is told to change nothing. It answers in a fixed shape (`VERDICT`): approved, and notes. A rule routes on it: approved, go to the end; not approved, go back to the builder with the notes, then through the tests and the reviewer again. `back()` caps it: three builds at most.

```
                       ┌► builder 1 ─┐
request ─► planner ────┼► builder 2 ─┼─► merge ─► tests ─⑂─► reviewer ─⑂─ approved ─► end
                       └► …         ─┘              ▲    │failed     │sent back
                                                    │    ▼           │
                                                    └─ builder ◄─────┘   (three builds at most)
```

In [`6_cycle.py`](./6_cycle.py), the reviewer's role and the verdict's shape are added:

```python
REVIEWER = """You are the reviewer in a small team that works on the shop, a small Python project: you're in its folder, and you work through the shell. You didn't write the change you're shown. Check it against the feature request, point by point: does it do everything the request asks, exactly, without breaking anything else? Read the code and run what you like, but only read: change nothing. Approve it only if it's complete and correct; if not, say in notes exactly what is wrong, for the builder."""
VERDICT = {"type": "json_schema", "schema": {"type": "object", "additionalProperties": False, "required": ["approved", "notes"],   # the verdict's shape
    "properties": {"approved": {"type": "boolean"}, "notes": {"type": "string"}}}}
```

the builder reads the notes when the work was sent back:

```python
    if state.get("approved") is False: brief += f"\n\nThe reviewer sent it back. Fix this:\n{state['notes']}"
```

`changes()` shows the reviewer what changed, as git sees it, and `reviewer()` is added:

```python
def changes():                                           # what's changed in the shop since the last commit, as a diff: edited files, then new ones
    new = subprocess.run("git ls-files --others --exclude-standard -- . ':!.graph'", shell=True, capture_output=True, text=True).stdout.split()
    return subprocess.run("git diff -- .", shell=True, capture_output=True, text=True).stdout + "".join(
        subprocess.run(f"git diff --no-index /dev/null {f}", shell=True, capture_output=True, text=True).stdout for f in new)

def reviewer(state):                                     # node: a different role, read-only; reads the request and the diff, writes a verdict
    verdict, tokens = agent(REVIEWER, f"Feature request: {state['request']}\n\nThe change:\n{changes()}", tools=[shell],
                            act=lambda call: run(call.input["cmd"], who="reviewer"), output_config={"format": VERDICT})
    return json.loads(verdict), tokens
```

and the reviewer joins the nodes, and the edges go round:

```python
NODES = {"planner": planner, "builders": builders, "merge": merge, "builder": builder, "tests": tests, "reviewer": reviewer}   # graph: the nodes, by name
def back(state):                                         # router: back to the builder, but three builds at most
    return "builder" if state["route"].count("builder") < 3 else END
EDGES = {"planner": "builders", "builders": "merge", "merge": "tests", "builder": "tests",   # edge: where each node leads; fan-out, then fan-in
         "tests": lambda state: "reviewer" if state["passed"] else back(state),   # router: passed → the reviewer, failed → the builder again
         "reviewer": lambda state: END if state["approved"] else back(state)}   # cycle: approved → end, sent back → the builder, then round again
```

Put the shop back, then run it:

```bash
uv run ../6_cycle.py
```

```
● planner    12.0s    2,876 tokens  → plan: {"summary": "Add gift wrap at £3 per item across prices.py, receipt.py a…
  builder 2 $ cat receipt.py; ls
  builder 1 $ cat prices.py; ls
  builder 3 $ cat test_shop.py; cat prices.py receipt.py; ls
  builder 2 $ cat > receipt.py <<'EOF'
  builder 1 $ cat > prices.py <<'EOF'
  builder 3 $ python3 - <<'E'
  ● builder 2   5.9s    8,284 tokens  → changed receipt.py: I updated `receipt.py` for gift wrap, but I couldn't run the tests succe…
  ● builder 1   7.0s    8,431 tokens  → changed prices.py: I added gift wrap to `prices.py` and changed nothing else. The 3 existin…
  ● builder 3   9.0s   10,215 tokens  → changed test_shop.py: I added the gift wrap tests to `test_shop.py`, but they can't pass here …
  3 builders at once; one after another they'd take 7.0 + 5.9 + 9.0 = 21.9s
● builders    9.0s   26,930 tokens  → built: [{"part": 1, "files": ["prices.py"], "changed": ["prices.py"], "seconds"…
● merge       0.0s        0 tokens  → merged: ["prices.py", "receipt.py", "test_shop.py"]; dropped: []
● tests       0.1s        0 tokens  → passed: true; tests: Ran 7 tests in 0.000s
  ⑂ router → reviewer
  reviewer $ cd shop 2>/dev/null; ls -la; git status --short; git log --oneline | head; grep -rn "total
  reviewer $ ls .graph; cat .graph/* | head -30; cat test_shop.py | head -20
● reviewer    6.4s   11,280 tokens  → approved: true; notes: The change meets every point in the request, and I found nothing wrong. …
  ⑂ router → end
■ done       27.4s   41,086 tokens  route: planner → builders → merge → tests → reviewer
```

This time the planner split the work three ways, with the tests as a part of their own, and the reviewer approved on the first round: the cycle wasn't needed. The reviewer read more than the diff: it listed `.graph` and read the graph's own state, because nothing stopped it. It's told to only read, and nothing makes it; production changes that.

The cycle is there for when the work is wrong, and it costs a full round each time it goes. In an earlier run, with a stricter version of its role and before this module had a `.gitignore`, the reviewer sent the work back twice: the diff it was shown included Python's compiled `__pycache__` files, and it wanted them gone. That run took 72 seconds and 86,759 tokens. A reviewer reviews what it's shown, so what goes into its edge matters.

The graph is now the same for every request: plan, build in parallel, merge, test, review. A one-line change goes through all of it. Letting the shape depend on the request is next: a model as the router.

### 7. Orchestrator: a model draws the graph as it goes

The last router is a model. The **orchestrator** is the same agent, with the nodes for tools: each node is offered as a tool with a description, and when the orchestrator calls one, `choose()` runs that node on the state and shows the orchestrator what it wrote. There are no edges in the code any more. The orchestrator reads what happened and decides what runs next, until it answers with a report. `MOST` caps how many nodes one request may run.

```
                          ┌─────────── orchestrator ───────────┐
                          │  reads what each node wrote, picks │
                          │     the next one, or finishes      │
                          └───┬─────┬──────┬──────┬──────┬─────┘
                              ▼     ▼      ▼      ▼      ▼
                         planner builders merge tests reviewer builder
```

In [`graph.py`](./graph.py), the edges are replaced by this:

```python
# ── router: a model ─────────────────────────────────────────────────────────
ORCHESTRATOR = """You lead a small team that works on the shop, a small Python project. You don't read or change code yourself: you decide who works next, by calling them as tools, one at a time, until the feature request is done and checked. After each one, you see what they wrote to the team's shared record. When the work is done, or can't be done, reply with a short report: what was done, and how you know it's right."""
TEAM = {"planner": "Reads the request and the code, and writes a plan, split into parts that can be built at the same time.",   # router: each node, offered as a tool
        "builders": "Builds every part of the plan at once, one builder per part, each in their own copy of the shop. Needs a plan. Their work isn't in the shop until merge.",
        "merge": "Brings the builders' work into the shop: each part's own files.",
        "builder": "One builder, working in the shop itself: builds the request, following the plan if there is one, and fixes whatever the last tests or review reported.",
        "tests": "Runs the shop's tests. Plain code, no model.",
        "reviewer": "Someone who didn't write the change reads it against the request, then approves it or sends notes back for the builder."}
team = [{"name": name, "description": does, "input_schema": {"type": "object", "required": ["why"],
         "properties": {"why": {"type": "string", "description": "why this one, now, in a few words"}}}} for name, does in TEAM.items()]
MOST = 12                                                # router: the most nodes one request may run

def run_graph(request):                                  # graph: the orchestrator draws it as it goes
    state = {"request": request, "route": []}            # state: it starts with the request
    def choose(call):                                    # router: the model picked a node; run it, and show the model what the node wrote
        if len(state["route"]) >= MOST: return f"Not run: {MOST} nodes is the most one request may use. Write your report."
        print(f"  ⑂ orchestrator → {call.name}: {call.input.get('why', '')}")
        try: return json.dumps(node(call.name, state), ensure_ascii=False)[:4000]
        except Exception as error: print(f"  ✗ {call.name} failed: {error!r}"); return f"{call.name} failed: {error!r}"   # a node that breaks: the model hears about it, and decides
    start = time.time()
    report, tokens = agent(ORCHESTRATOR, f"Feature request: {request}", tools=team, act=choose)
    TRACE.append(("orchestrator", time.time() - start - sum(seconds for _, seconds, _ in TRACE), tokens))   # trace: the router's own time and tokens
    print(f"● {'orchestrator':<9}{TRACE[-1][1]:6.1f}s {tokens:>8,} tokens  → report: {gist(report)}")
    return state

start = time.time()
state = run_graph(REQUEST)
print(f"■ done     {time.time() - start:6.1f}s {sum(tokens for _, _, tokens in TRACE):>8,} tokens  route: {' → '.join(state['route'])}")
```

`choose()` passes the orchestrator any error from a node as a tool result, so a node that breaks, or is called too early (the builders, with no plan yet), doesn't end the run: the orchestrator hears about it and decides.

Put the shop back, then run it:

```bash
uv run ../graph.py
```

`⑂` lines are the orchestrator's choices, with its reason:

```
  ⑂ orchestrator → planner: Start: need a plan for the feature
● planner    13.7s    3,094 tokens  → plan: {"summary": "Add a gift wrap charge of £3 per item, counting quantities.…
  ⑂ orchestrator → builders: Build the three independent parts in parallel
  builder 3 $ cat test_shop.py; ls
  builder 1 $ cat prices.py; ls
  builder 2 $ cat receipt.py; ls
  builder 2 $ cat > receipt.py <<'EOF'
  builder 1 $ cat > prices.py <<'EOF'
  builder 3 $ python3 - <<'EOF'
  ● builder 2   6.8s    8,787 tokens  → changed receipt.py: `receipt.py` now takes `gift_wrap`, but the tests fail to import in this…
  ● builder 1   7.7s    8,866 tokens  → changed prices.py: I added gift wrap to `prices.py`, and that is the only file I changed. T…
  ● builder 3   8.8s   10,295 tokens  → changed test_shop.py: I added the gift wrap tests to `test_shop.py`, but they don't run yet. T…
  3 builders at once; one after another they'd take 7.7 + 6.8 + 8.8 = 23.3s
● builders    8.8s   27,948 tokens  → built: [{"part": 1, "files": ["prices.py"], "changed": ["prices.py"], "seconds"…
  ⑂ orchestrator → merge: Bring the parts into the shop
● merge       0.0s        0 tokens  → merged: ["prices.py", "receipt.py", "test_shop.py"]; dropped: []
  ⑂ orchestrator → tests: Verify merged work
● tests       0.1s        0 tokens  → passed: true; tests: Ran 9 tests in 0.000s
  ⑂ orchestrator → reviewer: Independent check against request
  reviewer $ cd shop 2>/dev/null; ls -R . | head -50; git status --short; cat prices.py receipt.py; pyt
● reviewer    4.3s    6,459 tokens  → approved: true; notes: The change meets every point in the request. total(basket, gift_wrap=Tru…
● orchestrator   7.2s   21,715 tokens  → report: Gift wrap is added at £3 per item, and quantities count, so two mugs are…
■ done       34.1s   59,216 tokens  route: planner → builders → merge → tests → reviewer
```

It drew the same graph we wired by hand in step 6: plan, build in parallel, merge, test, review. It passes the hidden checks (6/6). The orchestrator itself made six model calls and used 21,715 tokens, a third of the run, to choose a route a fixed graph gets for free.

So when does a fixed graph beat a model-drawn one?

| | Fixed edges and rules | A model as the router |
|---|---|---|
| Cost | nothing: plain code | a model call per choice, and it rereads everything so far |
| Same input, same path | yes | not guaranteed |
| Testing it | test the rules like any code | evaluate it, like any model |
| Fits a new kind of request | only if you wired that path | can take a path nobody wired |
| Resuming after a crash | the state and the next node's name | the orchestrator's whole conversation too |

When you know the shape of the work, wire it: it's cheaper, faster, and the same every time. Let a model draw the graph when the right shape really depends on the request and you can't list the cases. Many systems mix the two: fixed edges where the path is known, a model only where it isn't.

That's all four primitives, and [`graph.py`](./graph.py) is a complete graph. What it lacks is proof: we've seen it do one task, once, and so far one agent did it in 7.5 seconds for 4,812 tokens. Checking is next.

## Evaluating the Graph

Will the graph do better than one agent? Every node we added costs calls and tokens, so it has to buy something back: better work, or the same work sooner. We give both the same four feature requests, each in a fresh copy of `shop/`, and check what was built with the hidden acceptance tests:

| Request | What it asks | Passes when |
|---|---|---|
| `gift_wrap` | £3 per item on the total, and its own line on the receipt | two totals and the receipt's last two lines are right |
| `three_for_two` | cards are 3 for 2, counted across lines, the cheapest free | five totals and a receipt's total line are right |
| `christmas` | the card offer, then 10% off for members on what's left from £20, gift wrap never discounted, and a receipt line for each, in order | five totals, including the £20 threshold after the card offer, and two receipts are right |
| `gift_receipt` | a receipt with no prices and no total | its lines are right, with no £ anywhere |

Every request also needs the shop's own tests to still pass. The checks were checked: a correct solution passes all of them, and the untouched shop fails every new one.

[`evaluate.py`](./evaluate.py) runs any systems you name, one agent and the graph by default. For each run it prints whether it passed, how many checks, the tokens and time from the run's own `■` line, and its route. When a run fails, it says which node let it through, from the run's state:

```python
# Evaluation: every feature request, for one agent and for the graph, each on a fresh copy of shop/,
# checked by the hidden acceptance tests: by what was built, not by what anyone says.
# uv run evaluate.py                                 one agent against the graph
# uv run evaluate.py 1_one_agent.py graph_prod.py    one agent against the production graph
import subprocess, sys, os, re, json, shutil, tempfile
from acceptance import REQUESTS, check

here = os.path.dirname(os.path.abspath(__file__))        # the module, wherever this is run from
systems = sys.argv[1:] or ["1_one_agent.py", "graph.py"]

def fresh():                                             # a fresh copy of shop/, in a git repo of its own, like a clean clone
    folder = tempfile.mkdtemp()
    shutil.copytree(os.path.join(here, "shop"), folder, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", ".graph"))
    shutil.copy(os.path.join(here, ".gitignore"), folder)
    subprocess.run("git init -q && git add . && git -c user.name=eval -c user.email=eval@example.com commit -qm start", shell=True, cwd=folder)
    return folder

def failed_at(folder, printed):                          # which node let it through, from the trace and the state
    if "■ done" not in printed:                          # it crashed: the last node that started
        return "crashed after " + (re.findall(r"^● (\S+)", printed, re.M) or ["the start"])[-1]
    if not os.path.exists(f"{folder}/.graph/state.json"): return "agent: said it was done"   # one agent: the only node
    state = json.load(open(f"{folder}/.graph/state.json"))
    if state.get("approved"): return "reviewer: approved it"
    if state.get("approved") is False: return "reviewer: still sending it back when the rounds ran out"
    if state.get("passed"): return "tests: passed it, nothing reviewed it"
    return "tests: still failing when the rounds ran out" if "passed" in state else f"route ended at {state['route'][-1:]}"

rows = []                                                # (system, passed, tokens, seconds), one per run
for name, (request, _) in REQUESTS.items():
    for system in systems:
        folder = fresh()
        printed = subprocess.run(["uv", "run", "-q", os.path.join(here, system), request], cwd=folder, capture_output=True, text=True).stdout
        results = check(name, folder)                    # the hidden tests, on what it built
        done = re.search(r"^■ done\s+([\d.]+)s\s+([\d,]+) tokens(?:\s+route: (.*))?$", printed, re.M)   # its own trace: time, tokens, route
        tokens, seconds = (int(done.group(2).replace(",", "")), float(done.group(1))) if done else (0, 0.0)
        ok = all(passed for _, passed in results)
        rows.append((system, ok, tokens, seconds))
        print(f"{name:14} {system:15} {'PASS' if ok else 'FAIL'} {sum(p for _, p in results)}/{len(results)} {tokens:>8,} tokens {seconds:6.1f}s  "
              + ("" if ok else failed_at(folder, printed)), flush=True)
        if done and done.group(3): print(f"{'':31}route: {done.group(3)}")
        for what, passed in results:
            if not passed: print(f"{'':31}✗ {what}")

print()
for system in systems:                                   # totals, per system
    mine = [row for row in rows if row[0] == system]
    print(f"{system:15} {sum(row[1] for row in mine)}/{len(mine)} passed {sum(row[2] for row in mine):>9,} tokens {sum(row[3] for row in mine):7.1f}s")
```

It copies `shop/` as it is, so put the shop back first, with `git checkout . && git clean -fd`. Then:

```bash
uv run ../evaluate.py
```

```
gift_wrap      1_one_agent.py  PASS 6/6    5,035 tokens    7.5s  
gift_wrap      graph.py        PASS 6/6   60,213 tokens   34.9s  
                               route: planner → builders → merge → tests → reviewer
three_for_two  1_one_agent.py  PASS 7/7    5,990 tokens   10.4s  
three_for_two  graph.py        PASS 7/7   47,142 tokens   36.3s  
                               route: planner → builders → merge → tests → reviewer
christmas      1_one_agent.py  PASS 8/8    7,423 tokens   15.6s  
christmas      graph.py        PASS 8/8   85,168 tokens   59.2s  
                               route: planner → builders → merge → tests → reviewer
gift_receipt   1_one_agent.py  PASS 5/5    5,022 tokens    5.4s  
gift_receipt   graph.py        PASS 5/5   34,812 tokens   26.7s  
                               route: planner → builders → merge → tests → reviewer

1_one_agent.py  4/4 passed    23,470 tokens    38.9s
graph.py        4/4 passed   227,335 tokens   157.1s
```

Both passed every request:

| | Passed | Tokens | Time |
|---|---|---|---|
| One agent | 4/4 | 23,470 | 38.9s |
| The graph | 4/4 | 227,335 (9.7×) | 157.1s (4.0×) |

Nothing failed, so there was no node to blame. The orchestrator drew the same route every time, the one we wired by hand in step 6. The tests never sent work back, and neither did the reviewer.

**On these four requests, the graph doesn't beat one agent.** It's as good, at about ten times the tokens and four times the time. That's the usual result for small, well-specified work: one agent holds the whole shop in its window, checks itself with tests, and is done in a handful of calls.

A mistake worth showing: the first time we ran the evaluation, we forgot the `git checkout .`, so every copy started with step 7's gift wrap already built. Those runs don't count, but two things in them were real. On gift wrap, the planner wrote that there was nothing to do, and the orchestrator skipped the builders: `planner → tests → reviewer`. A fixed graph would have built it again. And the reviewer sent christmas back once. By the builder's report of what it fixed, money was now rounded half-up in whole pence instead of in floating point, and `gift_wrap` was back as the second argument, so an old call like `total(basket, True)` still meant gift wrap. The hidden checks test neither, so the reviewer caught what our tests don't.

Run it after every change. A failing request tells you where to look, and its route tells you which node.

## Getting it Ready for Production

The graph works and passes its evaluation. But it costs ten times what one agent does for the same result. If it crashes halfway, it starts again from nothing. Its nodes can change anything in the shop: the reviewer is only *asked* not to. Once the screen scrolls past, there's no record of what each node did. And after a change, you can't tell if it still works.

Getting it ready means asking six questions of the graph:

| Question | Concern |
|---|---|
| Is a graph worth it here? | Fit, against the single agent |
| What if a node fails? | Resilience: checkpoints, retries, resume |
| What can each node touch? | Permissions, per node |
| What did each node do? | Observability: traces |
| Why is it slow or costly? | Performance: parallelism, effort per node |
| How do we know it still works? | Evaluation |

Each answer adds a few lines to the graph, marked with its question. The result is [`graph_prod.py`](./graph_prod.py).

### Is a graph worth it here?

For the four requests we evaluated, no. One agent passed all four with a tenth of the tokens, in a quarter of the time. If your work looks like the shop's, ship the single agent.

A graph earns its cost when it buys something one agent can't:

| A graph pays when | Because | In the shop |
|---|---|---|
| the work is bigger than one window | each node sees only its part | no: the whole shop fits in one read |
| a check must be independent | the reviewer didn't build it, and (below) can't change it | it approved every clean run; in the spoiled run it sent work back once, for two problems our checks don't test |
| the parts are big and independent | parallel builders save wall-clock time | the builders saved about 7 seconds, and the planner that split the work took 12 to 14 seconds |
| each step must be stopped, resumed, limited or inspected on its own | the structure lives outside the model | yes: the rest of this section |

When a graph is worth it, the evaluation also says which graph. The orchestrator drew the fixed route on every request, and in step 7 it used 21,715 of the run's 59,216 tokens to do it. So production keeps the graph and goes back to step 6's fixed edges. The orchestrator is the right tool when the routes really differ by request; here they didn't.

```python
EDGES = {"planner": "builders", "builders": "merge", "merge": "tests", "builder": "merge",   # worth it: fixed edges, as in step 6; permissions: the builder's work comes back through merge
         "tests": lambda state: "reviewer" if state["passed"] else back(state),   # router: passed → the reviewer, failed → the builder again
         "reviewer": lambda state: END if state["approved"] else back(state)}   # cycle: approved → end, sent back → the builder, then round again
```

### What if a node fails?

A graph has more places to fail than one agent, and more to lose: a crash in the reviewer means running the planner and the builders again. There are four layers, from the smallest failure to the largest.

A request to the model fails: the **client** sends it again, three times at most:

```python
client = Anthropic(max_retries=3)                        # failure: a request that fails is sent again, three times at most
```

A command hangs: `run()` stops it after two minutes, and the node hears that it was stopped:

```python
    try: done = subprocess.run(cmd, shell=True, cwd=folder, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace", timeout=120)
    except subprocess.TimeoutExpired: return "[stopped: it ran for over two minutes]"   # failure: a command that hangs doesn't hang its node
```

A node raises: `node()` runs it again, twice at most:

```python
    for attempt in (1, 2, 3):                            # failure: a node that raises gets two more tries
        try: update, tokens = NODES[name](state); break
        except Exception as error:
            if attempt == 3: raise
            print(f"  ✗ {name} failed, trying again: {error!r}")
```

The process dies: the state is already saved after every node, so it becomes a **checkpoint**: it now also records which node is next, and it's written whole or not at all. When the graph starts, `resume()` checks for an unfinished run of the same request, and carries on from there:

```python
def save(state):                                         # state: written after every node, so it can be read at any point
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE + ".new", "w") as f: json.dump(state, f, indent=2, ensure_ascii=False)
    os.replace(STATE + ".new", STATE)                    # failure: the checkpoint is written whole, or not at all

def resume(request):                                     # failure: an unfinished run of the same request carries on from its last checkpoint
    if not os.path.exists(STATE): return None
    state = json.load(open(STATE))
    if state.get("request") != request or state.get("at", END) == END: return None
    print(f"↻ resuming at {state['at']}, after {' → '.join(state['route'])}")
    return state
```

```python
def run_graph(request):                                  # graph: from the first node, follow the edges to the end
    state = resume(request) or {"request": request, "route": [], "at": "planner", "run": f"{datetime.datetime.now():%Y-%m-%dT%H-%M-%S}"}   # failure; observability: the run's name
    while state["at"] != END:
        at = state["at"]
        node(at, state)
        if not callable(EDGES[at]): state["at"] = EDGES[at]   # edge: a fixed edge, always taken
        else: state["at"] = EDGES[at](state); print(f"  ⑂ router → {state['at']}")   # router: a rule reads the state and picks the next node
        save(state)                                      # failure: a checkpoint after every node: what's done, and which node is next
    return state
```

We simulate a crash: while the builders are working, we kill the process with `kill -9`, which gives it no chance to clean up, as a power cut or running out of memory would. Here a script sent it two seconds after the first builder's first command; by hand, run `pkill -9 -f graph_prod.py` in another terminal.

Put the shop back, and start it:

```bash
uv run ../graph_prod.py
```

```
● planner     7.8s    2,219 tokens  → plan: {"summary": "Add gift wrap at £3 per item. prices.py gets a gift_wrap_co…
  builder 2 $ cat receipt.py prices.py test_shop.py; ls
  builder 1 $ cat prices.py test_shop.py; ls
```

It died with no message. The checkpoint says what was done, and what's next:

```bash
python3 -c "import json; s=json.load(open('.graph/state.json')); print('at:', s['at'], '| route:', s['route'])"
```

```
at: builders | route: ['planner']
```

Run it again:

```bash
uv run ../graph_prod.py
```

```
↻ resuming at builders, after planner
  builder 1 $ cat prices.py test_shop.py; ls
  builder 2 $ cat receipt.py prices.py test_shop.py; ls
  builder 1 $ python3 - <<'E'
  builder 2 $ cat > receipt.py <<'EOF'
  ● builder 1   8.3s    9,317 tokens  → changed test_prices.py, prices.py: Part 1 is done: `prices.total` now takes `gift_wrap=False`, and a new `g…
  ● builder 2  10.4s   10,241 tokens  → changed test_receipt.py, receipt.py: `receipt()` now takes `gift_wrap=False`, but the tests fail in my copy u…
  2 builders at once; one after another they'd take 8.3 + 10.4 = 18.7s
● builders   10.4s   19,558 tokens  → built: [{"part": "builder 1", "files": ["prices.py", "test_prices.py"], "change…
● merge       0.0s        0 tokens  → merged: ["test_prices.py", "prices.py", "test_receipt.py", "receipt.py"]; dropped: []
● tests       0.1s        0 tokens  → passed: true; tests: Ran 10 tests in 0.000s
  ⑂ router → reviewer
  reviewer $ find . -name "*.py" -not -path "./.git/*" | head -50; cat shop/*.py | head -100; grep -rn 
  reviewer $ ls -la; ls shop
  reviewer $ cat prices.py receipt.py test_shop.py; python -m unittest 2>&1 | tail -15; python -c "
● reviewer    8.7s   10,460 tokens  → approved: true; notes: The change does what the request asks. total(basket, gift_wrap=True) add…
  ⑂ router → end
■ done       19.2s   30,018 tokens  route: planner → builders → merge → tests → reviewer
```

The planner's work wasn't repeated: the plan was in the checkpoint. The builders started over, in fresh copies. Whatever the killed builders had done was in copies the shop never saw, because only `merge` writes to the shop. A node that dies halfway leaves nothing half-done behind. It passes the hidden checks (6/6).

In these runs no node raised, so the retries never fired; we saw only the crash.

### What can each node touch?

Each node should be able to do what its job needs, and no more, and that should be enforced by the code around it, not asked for in its prompt. Here's what each node could touch before, and what it can touch now:

| Node | Before | Now |
|---|---|---|
| planner | no tools: it can only write | the same |
| builders | its own copy; merge takes back only its own files | the same |
| builder, fixing | the shop itself | its own copy; only the plan's files come back, through merge |
| reviewer | the shop itself; asked to change nothing | a copy that's thrown away: nothing it runs can change the shop |
| tests, merge | plain code | the same |

`workspace()` makes a node's own copy of the shop, and `build_in_copy()` runs a builder in one, told which files are its own. The fixing builder now works the same way as the others:

```python
def builder(state):                                      # node: a model with the shell; reads the request, the plan and what was wrong, fixes it
    brief = f"Feature request: {state['request']}\n\nThe plan:\n{json.dumps(state['plan'], indent=2, ensure_ascii=False)}"
    if state.get("passed") is False: brief += f"\n\nThe tests failed after the last build. Fix them:\n{state['tests']}"
    if state.get("approved") is False: brief += f"\n\nThe reviewer sent it back. Fix this:\n{state['notes']}"
    files = sorted({f for part in state["plan"]["parts"] for f in part["files"]})   # permissions: only the plan's files may come back
    built, tokens = build_in_copy("builder", brief, files)   # permissions: in its own copy, like the builders
    return {"built": [built]}, tokens

def workspace():                                         # permissions: a node's own copy of the shop; nothing in it reaches the shop unless merge brings it
    copy = tempfile.mkdtemp()
    shutil.copytree(".", copy, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".graph", "__pycache__"))
    return copy

def build_in_copy(who, brief, files):                    # permissions: a builder in its own copy, told which files are its own
    copy, start = workspace(), time.time()
    report, tokens = agent(BUILDER, f"{brief}\nChange only {', '.join(files)}.", tools=[shell], act=lambda call: run(call.input["cmd"], copy, who))
    changed = [f for f in os.listdir(copy) if os.path.isfile(f"{copy}/{f}") and not (os.path.isfile(f) and filecmp.cmp(f"{copy}/{f}", f, shallow=False))]
    print(f"  ● {who} {time.time() - start:5.1f}s {tokens:>8,} tokens  → changed {', '.join(changed) or 'nothing'}: {gist(report)}")
    return {"part": who, "files": files, "changed": changed, "seconds": round(time.time() - start, 1), "report": report, "folder": copy}, tokens

def build_part(state, number, part):                     # one builder, for one part of the plan
    return build_in_copy(f"builder {number}", f"Feature request: {state['request']}\n\nThe plan:\n{json.dumps(state['plan'], indent=2, ensure_ascii=False)}\n\n"
                         f"You build part {number}: {part['task']}\nOther builders are building the other parts at the same time, in their own copies.", part["files"])
```

`merge()` is where it's enforced. Only a builder's own files come back:

```python
            else: dropped.append(f"{f} ({part['part']})")   # permissions: not its file, so left out
```

and the fixing builder's work now goes through it:

```python
EDGES = {"planner": "builders", "builders": "merge", "merge": "tests", "builder": "merge",   # worth it: fixed edges, as in step 6; permissions: the builder's work comes back through merge
         "tests": lambda state: "reviewer" if state["passed"] else back(state),   # router: passed → the reviewer, failed → the builder again
         "reviewer": lambda state: END if state["approved"] else back(state)}   # cycle: approved → end, sent back → the builder, then round again
```

The reviewer runs its commands in a copy that's deleted when it's done, and its role says so:

```python
def reviewer(state):                                     # node: a different role, read-only; reads the request and the diff, writes a verdict
    scratch = workspace()                                # permissions: read-only, enforced: its commands run in a copy that's thrown away
    verdict, tokens = agent(REVIEWER, f"Feature request: {state['request']}\n\nThe change:\n{changes()}", tools=[shell],
                            act=lambda call: run(call.input["cmd"], scratch, "reviewer"), output_config={"format": VERDICT})
    shutil.rmtree(scratch, ignore_errors=True)           # permissions: whatever it did there is gone
    return json.loads(verdict), tokens
```

```
Read the code and run what you like: your shell works in a copy of the shop that is thrown away afterwards, so nothing you change reaches the shop, and git isn't there: the change is the diff you're given.
```

In the resumed run above, the reviewer looked around before it read the code (`find`, then `ls`), as it did in step 6. This time it was looking around a copy, with no `.graph` and no repo in it.

These copies limit what reaches the shop, not what a command can do on your machine: a builder can still run anything, anywhere you can. To limit that too, run each node's commands in a container, as the production harness in [harness engineering](../harness-engineering/) does.

### What did each node do?

The screen shows the run as it happens, then it's gone. Now `node()` writes one line per node to a trace file, named for when the run started, in `.graph/`. A resumed run carries on in the same file, because the run's name is in the state:

```python
    os.makedirs(".graph", exist_ok=True)
    with open(f".graph/{state['run']}.jsonl", "a") as f: f.write(json.dumps({"time": f"{datetime.datetime.now():%H:%M:%S}",   # observability: a trace file per run
        "node": name, "seconds": round(TRACE[-1][1], 1), "tokens": tokens, "read": read, "wrote": len(json.dumps(update, ensure_ascii=False))}) + "\n")
```

A full run on gift wrap, from a clean shop with no `.graph` (`git checkout . && git clean -fd && rm -rf .graph`, so this run's trace is the only one):

```bash
uv run ../graph_prod.py
```

```
● planner     6.9s    2,035 tokens  → plan: {"summary": "Add gift wrap (£3 per item, quantities counted). prices.py …
  builder 2 $ cat receipt.py test_shop.py prices.py; ls
  builder 1 $ cat prices.py
  builder 1 $ cat > prices.py <<'EOF'
  builder 2 $ cat > receipt.py <<'EOF'
  ● builder 1   6.4s    7,184 tokens  → changed prices.py: I added gift wrap to `prices.py` and changed nothing else. The three exi…
  builder 2 $ d=$(mktemp -d); cp receipt.py test_shop.py $d; cat > $d/prices.py <<'EOF'
  ● builder 2   9.9s   13,476 tokens  → changed receipt.py, test_shop.py: I changed `receipt.py` and `test_shop.py`, but the tests only pass again…
  2 builders at once; one after another they'd take 6.4 + 9.9 = 16.3s
● builders    9.9s   20,660 tokens  → built: [{"part": "builder 1", "files": ["prices.py"], "changed": ["prices.py"],…
● merge       0.0s        0 tokens  → merged: ["prices.py", "receipt.py", "test_shop.py"]; dropped: []
● tests       0.1s        0 tokens  → passed: true; tests: Ran 7 tests in 0.000s
  ⑂ router → reviewer
  reviewer $ ls -R . | head -50; cat shop/*.py | head -150; cd shop && python -m unittest 2>&1 | tail -
  reviewer $ python -m unittest 2>&1 | tail -5; python -c "
● reviewer    5.8s    8,423 tokens  → approved: true; notes: The change does everything the request asks. total(basket, gift_wrap=Tru…
  ⑂ router → end
■ done       22.6s   31,118 tokens  route: planner → builders → merge → tests → reviewer
```

and its trace:

```bash
cat .graph/*.jsonl
```

```
{"time": "20:46:01", "node": "planner", "seconds": 6.9, "tokens": 2035, "read": 344, "wrote": 2173}
{"time": "20:46:11", "node": "builders", "seconds": 9.9, "tokens": 20660, "read": 2527, "wrote": 2107}
{"time": "20:46:11", "node": "merge", "seconds": 0.0, "tokens": 0, "read": 4643, "wrote": 70}
{"time": "20:46:11", "node": "tests", "seconds": 0.1, "tokens": 0, "read": 4722, "wrote": 130}
{"time": "20:46:16", "node": "reviewer", "seconds": 5.8, "tokens": 8423, "read": 4864, "wrote": 561}
```

`read` is how big the state was when the node started, in characters, and `wrote` is how much the node wrote to it. You can see the record grow, from the request alone (344) to everything the reviewer read (4,864), and where the tokens went: the builders used 20,660 of 31,118. With the state file, it answers what each node did, how long it took and what it cost, after the screen has scrolled past.

### Why is it slow or costly?

Two answers were already in the graph: plain code wherever no model is needed (tests and merge cost 0 tokens and a tenth of a second), and builders in parallel. In the full production run above, the two builders took 6.4 and 9.9 seconds: 16.3 one after another, 9.9 at once.

The production graph adds two more. The first is the fixed edges from the first question: the orchestrator's tokens are gone. The second is **effort**: how much the model thinks before it answers. The planner makes one call and writes a plan, so we tried it at low effort:

```python
EFFORT = {"planner": "low"}                              # cost: less thinking for the node that only writes a plan
```

```python
def planner(state):                                      # node: a model with no tools; reads the request, writes the plan, split into parts
    plan, tokens = agent(PLANNER, f"Feature request: {state['request']}\n\nThe code:\n{code()}", output_config={"format": PLAN, "effort": EFFORT["planner"]})   # cost
    return {"plan": json.loads(plan)}, tokens
```

Measured on the gift-wrap runs, not assumed:

| Planner | Tokens | Time |
|---|---|---|
| default effort (steps 5, 6, 7) | 2,972 · 2,876 · 3,094 | 14.3s · 12.0s · 13.7s |
| low effort (three production runs) | 2,035 · 2,219 · 2,140 | 6.9s · 7.8s · 7.3s |

About 30% fewer tokens and about half the time, and its plans still passed every hidden check, here and in the evaluation below. (The third low-effort run is the evaluation's gift wrap, read from the trace file it left behind.) One run each, the whole run went from 59,216 tokens and 34.1 seconds (`graph.py`, step 7) to 31,118 tokens and 22.6 seconds (`graph_prod.py`, above).

The builders are now most of the cost: each rereads the files and resends its conversation on every call. We didn't lower their effort, because they write the code, and we haven't measured what it would cost in quality. Two more cuts we didn't measure, so we don't claim numbers for them: prompt caching, so the repeated part of each builder's conversation costs less, and a smaller model for small parts.

### How do we know it still works?

Every answer changed the graph, and any change can change what it builds. The evaluation already answers this: put the shop back, and run the same requests on the production graph:

```bash
uv run ../evaluate.py graph_prod.py
```

```
gift_wrap      graph_prod.py   PASS 6/6   27,635 tokens   21.9s  
                               route: planner → builders → merge → tests → reviewer
three_for_two  graph_prod.py   PASS 7/7   13,823 tokens   17.5s  
                               route: planner → builders → merge → tests → reviewer
christmas      graph_prod.py   PASS 8/8  117,743 tokens   72.0s  
                               route: planner → builders → merge → tests → reviewer
gift_receipt   graph_prod.py   PASS 5/5   12,108 tokens   14.1s  
                               route: planner → builders → merge → tests → reviewer

graph_prod.py   4/4 passed   171,309 tokens   125.5s
```

Still 4 of 4, on every request:

| | Passed | Tokens | Time |
|---|---|---|---|
| One agent | 4/4 | 23,470 | 38.9s |
| `graph.py` | 4/4 | 227,335 | 157.1s |
| `graph_prod.py` | 4/4 | 171,309 | 125.5s |

A quarter fewer tokens and a fifth less time than `graph.py`, with the same results, and still about seven times the tokens of one agent. One run per request is a small sample: christmas cost more in production than before (117,743 tokens against 85,168). `evaluate.py` leaves each copy in a temporary folder, so its trace file says where they went: the builders used 84,749 of them.

Run it after every change, with the single agent beside it: `uv run ../evaluate.py 1_one_agent.py graph_prod.py`.

## What you built

You started with one agent that planned, built and judged its own work, and split it into a graph, one primitive at a time:

| Primitive | What it gave the shop |
|---|---|
| Node | roles: a planner that can't act, builders, a reviewer that didn't build it, and plain-code tests and merge that cost nothing |
| Edge | what each node gets to see: the plan to the builders, the diff to the reviewer |
| State | one record of the run, readable at any point, and a checkpoint to resume from |
| Router | a path that depends on what happened: back to the builder when the tests fail or the reviewer says no, or a path drawn by a model |

Then you evaluated it against one agent, found it no better on these requests at ten times the tokens, and got it ready for production by asking six questions, starting with whether it was worth it.

That's graph engineering. Every multi-agent framework is these four primitives, in some arrangement. LangGraph builds a graph of nodes and edges over a shared state, with conditional edges for its routers. Anthropic's guide *Building effective agents* names workflow patterns that are arrangements of them: prompt chaining is a chain, routing is a router, parallelization is a fan-out, orchestrator-workers is an orchestrator, and evaluator-optimizer is a cycle. A coding agent that hands work to subagents is an orchestrator whose nodes are agents. Open any of them and you'll find nodes, edges, state and a router.

## License

The code (the Python files and `shop/`) is under the [MIT License](../LICENSE). The written course (this README) is under [Creative Commons Attribution 4.0](../LICENSE-CC-BY-4.0) (CC BY 4.0): you can share and adapt it, for any purpose, as long as you credit Chase Dovey and link back to this repo.

Copyright © 2026 Chase Dovey.
