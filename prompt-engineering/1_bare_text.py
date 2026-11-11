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

# ── the request ─────────────────────────────────────────────────────────────
email = open(sys.argv[1]).read()                         # the email, exactly as the customer sent it
response = request_response(
    max_tokens=16384,                                    # settings: the most it may write
    thinking={"type": "between_tools"},                  # reasoning: none yet; it answers straight away
    messages=[{"role": "user", "content": email}])       # bare text: the email, and nothing else
for block in response.content:
    if block.type == "text": print(block.text)           # the answer
print(f"[{response.usage.input_tokens} tokens in, {response.usage.output_tokens} out]", file=sys.stderr)   # tokens in, tokens out
