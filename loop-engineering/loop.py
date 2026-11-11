# /// script
# dependencies = ["anthropic"]
# ///
import subprocess, sys, os, time, glob, json
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

# ── trigger ─────────────────────────────────────────────────────────────────
REQUEST = "Work through the backlog in BACKLOG.md."      # the request, the same every time

def arg(flag):                                           # trigger: the value after a flag on the command line, if it's there
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else None

def triggers():                                          # trigger: fires each time a run should start, and says why
    if arg("--every"):                                   # trigger: a schedule, every N seconds
        every, start = int(arg("--every")), time.time()
        while True:
            yield f"the schedule (every {every}s)"
            time.sleep(every - (time.time() - start) % every)   # trigger: sleep to the next tick; ticks a long run missed are skipped
    elif arg("--on"):                                    # trigger: an event, a file changing
        path = arg("--on")
        seen = os.path.getmtime(path)
        while True:
            time.sleep(1)
            if os.path.getmtime(path) != seen:
                yield f"{path} changing"
                seen = os.path.getmtime(path)            # trigger: changes made during the run don't count
    else:
        yield "you"                                      # trigger: a person starts the first run
        while True: yield "the last run ending"          # trigger: then each run's end starts the next

# ── check ───────────────────────────────────────────────────────────────────
def check():                                             # check: runs each feature's tests itself: what it did, not what it says
    tests = sorted(glob.glob("test_*.py"))               # check: a feature for each test file
    return {t[5:-3]: subprocess.run([sys.executable, "-m", "unittest", t[:-3]], capture_output=True, text=True) for t in tests}

def failures(results):                                   # check: what failed, in the tests' own words: the lines that name each failure
    return {name: [line for line in done.stderr.splitlines() if line.startswith(("FAIL:", "ERROR:")) or "Error: " in line]
            for name, done in results.items() if done.returncode}

def verdict(results):                                    # check: which features pass, as one line
    passing = [name for name, done in results.items() if not done.returncode]
    return f"── check: {len(passing)} of {len(results)} features pass: {', '.join(passing) or 'none'}"

# ── state ───────────────────────────────────────────────────────────────────
STATE = "progress.json"                                  # state: the handover sheet, kept in the work's own folder

def load():                                              # state: where things stand, as the last run left them
    return json.load(open(STATE)) if os.path.exists(STATE) else {"runs": 0, "tokens": 0, "stalled": 0}

def save(state, results, said, tokens):                  # state: what the next run should know, written down and committed
    before = state.get("features", {})
    state["runs"] += 1
    state["features"] = {name: not done.returncode for name, done in results.items()}   # state: passes, as the check found it
    state["failures"] = failures(results)                # state: what failed, in the tests' words
    state["notes"] = said                                # state: the run's final message, a note for the next
    state["tokens"] += tokens                            # stop: the budget's count, kept here so a restart can't reset it
    newly = [name for name, ok in state["features"].items() if ok and not before.get(name)]
    state["stalled"] = 0 if newly else state["stalled"] + 1   # stop: runs in a row with nothing newly passing
    json.dump(state, open(STATE, "w"), indent=2)
    passing = sum(state["features"].values())
    subprocess.run(f'git add -A && git -c user.name=loop -c user.email=loop@localhost commit -qm "run {state["runs"]}: {passing} of {len(results)} features pass"', shell=True)   # state: the run's work, in git

def request(state):                                      # state: the request, with where things stand
    if not state["runs"]: return REQUEST
    return f"{REQUEST}\n\nYou're one of a series of runs, each starting fresh. After each run, the tests are run and the work is committed to git. Where things stand, from {STATE}:\n\n{open(STATE).read()}"

# ── stop ────────────────────────────────────────────────────────────────────
MAX_RUNS = 8                                             # stop: the most runs, however it's going
BUDGET = 100_000                                         # stop: the most tokens, across all runs
PATIENCE = 2                                             # stop: runs in a row with nothing newly passing, before asking a person

def stop(state):                                         # stop: a reason to end, or None to go on
    if state["runs"] and all(state["features"].values()): return "done: every feature's tests pass"
    if state["runs"] >= MAX_RUNS: return f"out of runs: {state['runs']} of {MAX_RUNS}"
    if state["tokens"] >= BUDGET: return f"out of budget: {state['tokens']:,} of {BUDGET:,} tokens"
    if state["stalled"] >= PATIENCE: return f"no progress: {state['stalled']} runs in a row with nothing newly passing"

def ask_a_person(reason, state):                         # stop: not done, so leave a note for a person
    failing = [name for name, ok in state["features"].items() if not ok]
    open("HELP.md", "w").write(f"# The loop stopped, and needs a person\n\nWhy: {reason}.\nStill failing: {', '.join(failing)}.\n"
                               f"Where things stand: {STATE}. What each run did: git log.\n")

# ── the outer loop ──────────────────────────────────────────────────────────
for why in triggers():                                   # outer loop: a run each time the trigger fires
    state = load()                                       # state: read fresh from disk before every run
    reason = stop(state)                                 # stop: before every run, is there a reason to end?
    if reason: break
    print(f"── run {state['runs'] + 1}, started by {why}, at {time.strftime('%H:%M:%S')}", flush=True)
    said, tokens = run(request(state))                   # the agent: one run, a black box
    print(f"── run {state['runs'] + 1} is over: {tokens:,} tokens", flush=True)
    results = check()                                    # check: after every run, the tests decide
    print(verdict(results), flush=True)
    save(state, results, said, tokens)                   # state: written down, for the next run
if not reason.startswith("done"): ask_a_person(reason, state)   # stop: anything but done needs a person
print(f"── stopped, {reason}: {state['runs']} runs, {state['tokens']:,} tokens", flush=True)
