# Evaluation: emails with known right answers, each run several times, every record checked field by field, by code.
# uv run evaluate.py                                                    evaluates prompt.py on orders/emails/
# uv run evaluate.py 6_format.py                                        evaluates another prompt file
# uv run evaluate.py prompt_prod.py orders/emails orders/production     adds the production emails
import subprocess, sys, json, glob, os
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

prompt = sys.argv[1] if len(sys.argv) > 1 else "prompt.py"
folders = sys.argv[2:] or ["orders/emails"]
answers = json.load(open("orders/answers.json"))         # the right record for every email
emails = sorted(path for folder in folders for path in glob.glob(f"{folder}/*.txt"))
N = 5                                                    # runs per email: the same prompt can answer differently each time

def run(path):                                           # one run of the prompt file on one email: what it printed should be a record
    printed = subprocess.run(["uv", "run", "-q", prompt, path], capture_output=True, text=True).stdout
    try: return json.loads(printed)
    except json.JSONDecodeError: return None

def items(record):                                       # the items as (product, quantity) pairs, in a fixed order
    return sorted((item.get("product"), item.get("quantity")) for item in record.get("items") or [])

def wrong(record, answer):                               # what doesn't match the right answer, field by field
    if not isinstance(record, dict): return ["not JSON"]
    fields = []
    if str(record.get("customer", "")).strip().lower() != answer["customer"].lower(): fields.append("customer")
    if items(record) != items(answer): fields.append("items")
    if record.get("discount_code") != answer["discount_code"]: fields.append("discount_code")
    if "question" in answer and bool(record.get("question")) != answer["question"]: fields.append("question")
    return fields

with ThreadPoolExecutor(8) as pool:                      # every run of every email, eight at a time
    records = list(pool.map(run, [path for path in emails for _ in range(N)]))

total = 0
for i, path in enumerate(emails):
    answer = answers[os.path.basename(path)]
    misses = [wrong(record, answer) for record in records[i * N:(i + 1) * N]]
    passed = sum(not miss for miss in misses)
    total += passed
    why = Counter(field for miss in misses for field in miss)
    line = f"{'PASS' if passed == N else 'FAIL'}  {passed}/{N}  {os.path.basename(path)}  {answer['case']:<36}  "
    print((line + ", ".join(f"{field} in {count}" for field, count in why.items())).rstrip(), flush=True)
print(f"{total}/{len(emails) * N} runs passed")
