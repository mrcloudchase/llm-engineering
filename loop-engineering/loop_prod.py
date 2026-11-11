# /// script
# dependencies = ["anthropic"]
# ///
import subprocess, sys, os, time, glob, json, shutil, fcntl
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
    messages, tokens, cached = [{"role": "user", "content": request}], 0, 0   # agent: a fresh context, nothing from any earlier run
    for turn in range(SHIFT):                            # agent: the inner loop, model ↔ tools, one turn at a time
        home = turn == SHIFT - 1                         # agent: the shift's last turn: words only, no commands
        if home: messages[-1]["content"].append({"type": "text", "text": HOME_TIME})
        response = request_response(max_tokens=16384, tools=tools, messages=messages, tool_choice={"type": "none" if home else "auto"},
                                    cache_control={"type": "ephemeral"})   # cost: each turn reuses what the last turn already sent
        usage = response.usage
        tokens += usage.input_tokens + usage.cache_creation_input_tokens + usage.cache_read_input_tokens + usage.output_tokens   # cost: every token, cached or not
        cached += usage.cache_read_input_tokens          # cost: the tokens read back from the cache, at a tenth of the price
        messages.append({"role": "assistant", "content": response.content})
        results = handle_output(response.content)
        if not results: break                            # agent: it asked for no commands: the run is over
        messages.append({"role": "user", "content": results})
    return "\n".join(b.text for b in response.content if b.type == "text"), tokens, cached

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
        if not os.path.realpath(path).startswith(os.path.realpath(".") + os.sep): sys.exit("── only a file in this folder can start a run")   # trigger: no outside source
        seen = os.path.getmtime(path)
        while True:
            time.sleep(1)
            if os.path.getmtime(path) != seen:
                yield f"{path} changing"
                seen = os.path.getmtime(path)            # trigger: changes made during the run don't count
    else:
        yield "you"                                      # trigger: a person starts the first run
        while True: yield "the last run ending"          # trigger: then each run's end starts the next

LOOP_DIR = os.path.expanduser("~/.loop/" + os.getcwd().strip(os.sep).replace(os.sep, "-"))   # the loop's own files, outside the folder the agent works in

def lock():                                              # trigger: one loop per folder, so two runs never overlap
    handle = open(os.path.join(LOOP_DIR, "lock"), "w")
    try: fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError: sys.exit("── another loop is already running in this folder")
    return handle                                        # trigger: held until this process ends, however it ends

# ── check ───────────────────────────────────────────────────────────────────
PROTECTED = os.path.join(LOOP_DIR, "tests")              # cheating: the tests as they were when the loop first started here

def protect():                                           # cheating: copy the tests out of the folder, once
    if os.path.exists(PROTECTED): return
    os.makedirs(PROTECTED)
    for test in glob.glob("test_*.py"): shutil.copy(test, PROTECTED)

def restore():                                           # cheating: put back any test a run changed or deleted, and say which
    tampered = []
    for kept in sorted(glob.glob(os.path.join(PROTECTED, "test_*.py"))):
        test = os.path.basename(kept)
        if not os.path.exists(test) or open(test).read() != open(kept).read():
            tampered.append(test)
            shutil.copy(kept, test)
    return tampered

def check():                                             # check: runs each feature's tests itself: what it did, not what it says
    tests = sorted(os.path.basename(t) for t in glob.glob(os.path.join(PROTECTED, "test_*.py")))   # cheating: the features are the protected tests
    return {t[5:-3]: subprocess.run([sys.executable, "-m", "unittest", t[:-3]], capture_output=True, text=True) for t in tests}

def failures(results):                                   # check: what failed, in the tests' own words: the lines that name each failure
    return {name: [line for line in done.stderr.splitlines() if line.startswith(("FAIL:", "ERROR:")) or "Error: " in line]
            for name, done in results.items() if done.returncode}

def verdict(results):                                    # check: which features pass, as one line
    passing = [name for name, done in results.items() if not done.returncode]
    return f"── check: {len(passing)} of {len(results)} features pass: {', '.join(passing) or 'none'}"

def roll_back(state, results):                           # spinning: a run that breaks a passing feature is undone
    broke = [name for name, ok in state.get("features", {}).items() if ok and results[name].returncode]
    if broke: subprocess.run("git reset -q --hard && git clean -fdq", shell=True)   # spinning: back to the last run's commit
    return broke

# ── state ───────────────────────────────────────────────────────────────────
STATE = "progress.json"                                  # state: the handover sheet, kept in the work's own folder

def load():                                              # state: where things stand, as the last run left them
    return json.load(open(STATE)) if os.path.exists(STATE) else {"runs": 0, "tokens": 0, "stalled": 0, "best": 0}

def save(state, results, said, tokens):                  # state: what the next run should know, written down and committed
    state["runs"] += 1
    state["features"] = {name: not done.returncode for name, done in results.items()}   # state: passes, as the check found it
    state["failures"] = failures(results)                # state: what failed, in the tests' words
    state["notes"] = said                                # state: the run's final message, a note for the next
    state["tokens"] += tokens                            # stop: the budget's count, kept here so a restart can't reset it
    passing = sum(state["features"].values())
    state["stalled"] = 0 if passing > state["best"] else state["stalled"] + 1   # spinning: progress is more passing than ever before
    state["best"] = max(state["best"], passing)
    json.dump(state, open(STATE, "w"), indent=2)
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
    if state["stalled"] >= PATIENCE: return f"no progress: {state['stalled']} runs in a row without more features passing than before"

def ask_a_person(reason, state):                         # stop: not done, so leave a note for a person
    failing = "".join(f"- {name}: {' '.join(lines[-1:])}\n" for name, lines in state["failures"].items())   # spinning: what's stuck, in the tests' words
    open("HELP.md", "w").write(f"# The loop stopped, and needs a person\n\nWhy: {reason}.\n\nStill failing:\n{failing}\n"
                               f"The last run's notes:\n\n{state['notes']}\n\nWhere things stand: {STATE}. Every run: {LOG}. What each run changed: git log -p.\n")

# ── observability ───────────────────────────────────────────────────────────
LOG = os.path.join(LOOP_DIR, "runs.jsonl")               # observability: one line per run, outside the folder

def log(**line):                                         # observability: what a run did, as the loop saw it
    with open(LOG, "a") as f: f.write(json.dumps({"time": time.strftime("%Y-%m-%dT%H:%M:%S"), **line}) + "\n")

def report(reason, state):                               # observability: what happened while you were away, in one page
    runs = [json.loads(line) for line in open(LOG)] if os.path.exists(LOG) else []
    rows = "".join(f"| {r['run']} | {r['trigger']} | {r['minutes']} | {r['tokens']:,} | {r['cached']:,} | {r['passing']} | {', '.join(r['newly']) or '-'} | "
                   f"{', '.join(r['broke']) or '-'} | {', '.join(r['tampered']) or '-'} |\n" for r in runs)
    open("REPORT.md", "w").write(f"# What the loop did\n\nStopped: {reason}. {state['runs']} runs, {state['tokens']:,} tokens.\n\n"
                                 "| Run | Started by | Minutes | Tokens | Cached | Passing | New | Broke, so undone | Tests put back |\n|---|---|---|---|---|---|---|---|---|\n" + rows)

# ── the outer loop ──────────────────────────────────────────────────────────
os.makedirs(LOOP_DIR, exist_ok=True)
held = lock()                                            # trigger: refuse to start if a loop already runs here
protect()                                                # cheating: the tests, copied out before any run can touch them
if "--check" in sys.argv:                                # observability: where things stand, without starting a run
    tampered = restore()                                 # cheating: the protected tests first, as before every check
    print(verdict(check()) + f"; put back: {', '.join(tampered) or 'none'}")
    sys.exit()
for why in triggers():                                   # outer loop: a run each time the trigger fires
    state = load()                                       # state: read fresh from disk before every run
    reason = stop(state)                                 # stop: before every run, is there a reason to end?
    if reason: break
    print(f"── run {state['runs'] + 1}, started by {why}, at {time.strftime('%H:%M:%S')}", flush=True)
    started = time.time()
    said, tokens, cached = run(request(state))           # the agent: one run, a black box
    print(f"── run {state['runs'] + 1} is over: {tokens:,} tokens, {cached:,} of them cached", flush=True)
    tampered = restore()                                 # cheating: the tests go back as they were before the check runs
    results = check()                                    # check: after every run, the tests decide
    broke = roll_back(state, results)                    # spinning: never keep a run that broke what passed
    if broke: results, said = check(), f"[The loop undid this run's changes: they broke {', '.join(broke)}.]\n\n{said}"   # spinning: the next run hears why
    print(verdict(results) + (f"; broke {', '.join(broke)}, so the run was undone" if broke else "") + (f"; put back {', '.join(tampered)}" if tampered else ""), flush=True)
    newly = [name for name, done in results.items() if not done.returncode and not state.get("features", {}).get(name)]
    save(state, results, said, tokens)                   # state: written down, for the next run
    log(run=state["runs"], trigger=why, minutes=round((time.time() - started) / 60, 1), tokens=tokens, cached=cached,   # observability
        passing=f"{sum(state['features'].values())} of {len(results)}", newly=newly, broke=broke, tampered=tampered, notes=said)
if not reason.startswith("done"): ask_a_person(reason, state)   # stop: anything but done needs a person
report(reason, state)                                    # observability: the one page to read when you're back
print(f"── stopped, {reason}: {state['runs']} runs, {state['tokens']:,} tokens; see REPORT.md", flush=True)
