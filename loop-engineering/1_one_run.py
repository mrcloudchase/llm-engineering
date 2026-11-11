# /// script
# dependencies = ["anthropic"]
# ///
import subprocess, sys
from anthropic import Anthropic

# ── the agent: one run ──────────────────────────────────────────────────────
client = Anthropic()
MODEL = "claude-sonnet-5-5"
def request_response(**request):                         # model interface: requests a response from the model
    return client.messages.create(model=MODEL, **request)

tools = [{"name": "shell", "description": "Run a shell command", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]
SHIFT = 4                                                # agent: the most turns one run gets, a shift's fixed length
HOME_TIME = "[Your shift is over: no more commands. Say what you did, and what's left.]"

def show(text):                                          # agent: the model's words, after >
    print("> " + text.replace("\n", "\n  "), flush=True)

def nested(result, keep=8):                              # agent: what a command printed, under it with └, cut short on screen
    lines = result.rstrip("\n").split("\n")
    if len(lines) > keep: lines = lines[:keep] + [f"… ({len(lines) - keep} more lines)"]
    return "  └ " + "\n    ".join(lines)

def handle_output(output):                               # agent: runs each command the model asks for
    results = []
    for block in output:
        if block.type == "text": show(block.text)
        if block.type == "tool_use":
            print(f"$ {block.input['cmd']}", flush=True)
            done = subprocess.run(block.input["cmd"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
            result = done.stdout or f"(exit {done.returncode})"
            print(nested(result), flush=True)
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": result})
    return results

def run(request):                                        # agent: one run, from a fresh start: a request in, a final message out
    messages, tokens = [{"role": "user", "content": request}], 0   # agent: a fresh context, nothing from any earlier run
    for turn in range(SHIFT):                            # agent: the inner loop, model ↔ tools, one turn at a time
        home = turn == SHIFT - 1                         # agent: the shift's last turn: words only, no commands
        if home: messages[-1]["content"].append({"type": "text", "text": HOME_TIME})
        response = request_response(max_tokens=16384, tools=tools, messages=messages, tool_choice={"type": "none" if home else "auto"})
        tokens += response.usage.input_tokens + response.usage.output_tokens
        messages.append({"role": "assistant", "content": response.content})
        results = handle_output(response.content)
        if not results: break                            # agent: it asked for no commands: the run is over
        messages.append({"role": "user", "content": results})
    return "\n".join(b.text for b in response.content if b.type == "text"), tokens

# ── by hand ─────────────────────────────────────────────────────────────────
request = " ".join(sys.argv[1:]) or input("< ")          # a person starts the run, with a request
said, tokens = run(request)                              # one run: work, then a final message
print(f"── the run is over: {tokens:,} tokens")
