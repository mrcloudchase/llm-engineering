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
