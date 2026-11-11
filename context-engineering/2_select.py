# /// script
# dependencies = ["anthropic"]
# ///
import collections, glob, math, re, sys
from anthropic import Anthropic, BadRequestError

# ── model interface ─────────────────────────────────────────────────────────
client = Anthropic()
MODEL = "claude-sonnet-5-5"
def request_response(**request):                         # model interface: requests a response from the model
    return client.messages.create(model=MODEL, **request)

def tokens(request):                                     # model interface: how many tokens a request would put in the window
    return client.messages.count_tokens(model=MODEL, **request).input_tokens

# ── source ──────────────────────────────────────────────────────────────────
INSTRUCTIONS = "You work at the help desk of Hearth & Pine, a shop that sells home goods. Answer the customer's question from the handbook pages you're given. If they don't hold the answer, say so."

def load(path):                                          # source: one page of the handbook, as a chunk
    updated, text = open(path).read().split("\n\n", 1)   # source: a page's first line says when it was last updated
    return {"source": path.removeprefix("handbook/"), "date": updated.removeprefix("updated: "), "text": text}
CHUNKS = [load(path) for path in sorted(glob.glob("handbook/**/*.md", recursive=True))]   # source: every page of the handbook

# ── select ──────────────────────────────────────────────────────────────────
K = 3                                                    # select: how many pages each question gets
WINDOW = 8_000                                           # our own window: the most tokens we mean one call to hold

def words(text):                                         # select: a text's words, lowercase, with plurals folded in ("boards" finds "board")
    return {w[:-1] if len(w) > 3 and w.endswith("s") else w for w in re.findall(r"[a-z0-9]+", text.lower())}
WORDS = [words(chunk["text"]) for chunk in CHUNKS]       # select: each page's words, found once
PAGES_WITH = collections.Counter(w for page in WORDS for w in page)   # select: how many pages each word is on
RARITY = {w: math.log(len(CHUNKS) / n) for w, n in PAGES_WITH.items()}   # select: a word on every page scores 0; a word on one page, the most

def select(question, k=K):                               # select: the k pages that share the rarest words with the question
    asked = words(question)
    scores = [sum(RARITY[w] for w in asked & page) for page in WORDS]
    chosen = [CHUNKS[i] for i in sorted(range(len(CHUNKS)), key=lambda i: -scores[i])[:k]]
    size = tokens({"messages": [{"role": "user", "content": "\n\n".join(chunk["text"] for chunk in chosen)}]})   # select: how many tokens they take
    print(f"[selected {k} of {len(CHUNKS):,} pages, {size:,} tokens: {', '.join(chunk['source'] for chunk in chosen)}]")
    return chosen

# ── context ─────────────────────────────────────────────────────────────────
def assemble(question, history):                         # context: the instructions, the pages selected for this question, then the question
    pages = "\n\n".join(chunk["text"] for chunk in select(question))
    return {"messages": history + [{"role": "user", "content": f"{INSTRUCTIONS}\n\n{pages}\n\n{question}"}]}

# ── input ───────────────────────────────────────────────────────────────────
def capture_input():                                     # input: a one-off question on the command line, or what a person types
    if len(sys.argv) > 1: return " ".join(sys.argv[1:])
    line = ""
    while not line.strip():
        line = input("< ")                               # Ctrl-D, or the end of a piped session, ends it
        if not sys.stdin.isatty(): print(line)           # input: a piped session shows what was asked
    return line

# ── output ──────────────────────────────────────────────────────────────────
def show(response):                                      # output: the model's words, after >
    answer = "".join(block.text for block in response.content if block.type == "text")
    print("> " + answer.replace("\n", "\n  "))
    return answer

# ── session ─────────────────────────────────────────────────────────────────
def session():                                           # a person asks, it answers, and the session goes on
    history = []                                         # the conversation so far
    while True:
        try: question = capture_input()
        except EOFError: break                           # the person is done
        request = assemble(question, history)
        print(f"[window: {tokens(request):,} of {WINDOW:,} tokens]")
        try:
            answer = show(request_response(max_tokens=4096, **request))
            history = request["messages"] + [{"role": "assistant", "content": answer}]
        except BadRequestError as e:                     # the API turned the request away
            print(f"[rejected: {e.body['error']['message']}]")
        if len(sys.argv) > 1: break                      # a one-off question is done

session()
