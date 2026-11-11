# /// script
# dependencies = ["anthropic"]
# ///
import sys
from anthropic import Anthropic

# ── model interface ─────────────────────────────────────────────────────────
client = Anthropic()
MODEL = "claude-sonnet-5-5"
def request_response(**request):                         # model interface: requests a response from the model
    return client.messages.create(model=MODEL, **request)

# ── role ────────────────────────────────────────────────────────────────────
ROLE = "You work at the order desk of a small online tea shop. The shop's staff forward you the emails customers send."   # role: who it is, and who it works for

# ── the request ─────────────────────────────────────────────────────────────
email = open(sys.argv[1]).read()                         # the email, exactly as the customer sent it
response = request_response(
    max_tokens=16384,                                    # settings: the most it may write
    thinking={"type": "between_tools"},                  # reasoning: none yet; it answers straight away
    system=ROLE,                                         # role: who it is, and who it works for
    messages=[{"role": "user", "content": email}])       # role: the email, as the user's turn
for block in response.content:
    if block.type == "text": print(block.text)           # the answer
print(f"[{response.usage.input_tokens} tokens in, {response.usage.output_tokens} out]", file=sys.stderr)   # tokens in, tokens out
