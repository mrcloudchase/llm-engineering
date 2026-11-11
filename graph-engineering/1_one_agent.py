# /// script
# dependencies = ["anthropic"]
# ///
import subprocess, sys, time
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

# ── one agent does it all ───────────────────────────────────────────────────
REQUEST = " ".join(sys.argv[1:]) or ("Add gift wrap at £3 per item. total(basket, gift_wrap=True) adds £3 for every item, counting quantities "
    "(two mugs are two items). receipt(basket, gift_wrap=True) shows the charge on its own line, like 'Gift wrap: £6.00', just above "
    "the total, and the total includes it.")             # the feature request: from the command line, or gift wrap

ENGINEER = """You are a software engineer. You're in the folder of the shop, a small Python project, and you work through the shell. Plan the change you're asked for, make it, and check your work. Then reply with a short report: what you changed, and whether the request is done."""

start = time.time()
answer, tokens = agent(ENGINEER, REQUEST, tools=[shell]) # one node: plans, builds and judges its own work
print(f"● agent    {time.time() - start:6.1f}s {tokens:>8,} tokens")
print("> " + answer.replace("\n", "\n  "))
print(f"■ done     {time.time() - start:6.1f}s {tokens:>8,} tokens")
