# Evaluation: questions with known answers, each asked once in a fresh folder (no memory carries over),
# checked by what the answer says, with the tokens every window held to produce it.
# uv run evaluate.py                    evaluates context.py
# uv run evaluate.py 5_store.py         evaluates any step from 2 on
import json, os, re, subprocess, sys, tempfile

here = os.path.dirname(os.path.abspath(__file__))        # the module, wherever this is run from
script = sys.argv[1] if len(sys.argv) > 1 else "context.py"
questions = json.load(open(os.path.join(here, "questions.json")))

def right(answer, q):                                    # every expected piece is there, and nothing that mustn't be
    return all(a.lower() in answer.lower() for a in q["answer"]) and not any(n.lower() in answer.lower() for n in q.get("not", []))

passed = spent = 0
for q in questions:
    os.chdir(tempfile.mkdtemp())                         # a fresh folder that sees the same handbook
    os.symlink(os.path.join(here, "handbook"), "handbook")
    out = subprocess.run(["uv", "run", "-q", os.path.join(here, script), q["question"]], capture_output=True, text=True).stdout
    found = re.search(r"^> .*?(?=^\[|\Z)", out, re.S | re.M)   # the model's words: from > to the next [ line
    answer = found.group(0) if found else ""
    tokens = sum(int(n.replace(",", "")) for n in re.findall(r"window: ([\d,]+) of", out))   # every window it took: the reader's and the main one
    ok = right(answer, q)
    passed, spent = passed + ok, spent + tokens
    print(f"{'PASS' if ok else 'FAIL'}  {tokens:>6,} tokens  {q['question']}", flush=True)
print(f"{passed}/{len(questions)} right, {spent // len(questions):,} tokens per answer")
