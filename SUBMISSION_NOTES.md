# Submission notes: Nebius x NVIDIA Global AI Hackathon

Working notes for the Devpost entry. Not part of the product.

## (a) Devpost fields, draft

**Inspiration**

An LLM can write a convincing explanation for a payments discrepancy in a few
seconds. In finance that is the dangerous part: a wrong explanation that sounds
right gets a case closed and money goes missing. I wanted to see what it takes
to use a model for the hard reconciliation cases without ever trusting it as the
source of financial truth.

**What it does**

LedgerGuard reconciles orders, payments, refunds, settlements and bank entries.
A deterministic engine and an independent Shadow Ledger resolve everything that
can be proved with identifiers and arithmetic; on the frozen holdout that is 54
of 85 cases, with no AI involved. Only the cases they cannot prove go to the
model, here NVIDIA Nemotron on Nebius Token Factory. The model returns a
structured hypothesis and points at the records that would prove it. An
Evidence Gate then checks those records itself: does the refund exist, does it
belong to this payment, does the amount restore the ledger. If the proof is not
there, the case goes to a human instead of being closed. The output includes a
list of what it could not resolve and why.

**How I built it**

Python, FastAPI and Pydantic, with all money as integer paise. A seeded
synthetic generator produces lifecycles with known ground truth and six injected
fault classes, split into development and a frozen holdout. The AI step sits
behind one interface, `investigate(context) -> InvestigationResult`, so the
model host is a configuration choice. Nemotron is reached through Token
Factory's OpenAI compatible chat completions API using httpx. The dashboard is a
single HTML page served by the backend.

**What is new for this hackathon**

LedgerGuard was built in September 2026 for the Razorpay AI Buildathon. For this
hackathon I added a Nebius Token Factory provider that runs the investigator on
NVIDIA Nemotron, made it the first choice when its key is present, made the
response parser handle reasoning text that thinking models put before the
answer, added a one command evaluation of Nemotron on the same frozen holdout,
added offline tests for the new provider, and added an MIT license. The
engine, Shadow Ledger and Evidence Gate are unchanged, which is the point: the
model can be swapped and the safety property does not depend on which model it
is.

**Challenges**

The hard case is a refund whose amount exactly matches a shortfall but which
belongs to a different payment. Models tend to call it a partial refund. In the
September runs, across five investigators, 25 of 30 such attempts would have
been closed without the gate and 0 were closed with it. Getting the gate to
reject on linkage, not on amount, and keeping that protected by a test, took
more care than anything else. On the provider side, different hosts disagree on
which structured output modes they accept, so every host has to degrade to
human review rather than crash when its output does not parse.

**What's next**

Confirm which Nemotron models on Token Factory support strict JSON schema
output and switch to it where they do. Run the comparison on more than one
Nemotron size. Replace the synthetic settlement data with real settlement files
from a test account.

## (b) Every code change, in plain words

**`ledgerguard/ai/openai_compatible.py`**

- New `"nebius"` entry in `PRESETS`. A preset is just four facts about a host:
  the base URL (`https://api.tokenfactory.nebius.com/v1`), which environment
  variable holds the key (`NEBIUS_API_KEY`), the list of models to try in order,
  and whether the host accepts strict JSON schema output. The existing provider
  class reads these, so no new class was needed.
- The model list has two Nemotron models. If the first one fails (rate limit,
  not found, unparseable output), the provider moves to the second. Both are
  NVIDIA models, so a fallback never quietly switches to a non NVIDIA model.
  `LEDGERGUARD_MODEL` replaces the list with one model you choose.
- `"json_schema": False` means requests ask for `{"type": "json_object"}` and
  the schema is written into the system prompt. I chose this because the Token
  Factory docs contradict each other on strict schema mode, and json_object is
  the mode both pages agree on. The output is still validated against the
  schema in code, so a bad answer becomes "invalid response", never a closed
  case.
- `_strip_fences` now keeps only the text after the last `</think>`. Some
  reasoning models write their thinking into the answer field before the JSON.
  Without this, a correct answer would fail to parse and the case would go to
  human review for a formatting reason.

**`ledgerguard/ai/provider.py`**

- `"nebius"` added at the front of `AUTO_ORDER`. In the default `auto` mode the
  system builds a chain of every provider that has a key. Putting Nebius first
  means Nemotron answers when its key is set, and the free tier providers are
  only used if Nemotron fails. With no Nebius key it is skipped and nothing
  changes.
- The comment above it and the `get_provider` help text now mention Nebius, and
  the comment no longer says every provider is free, because Token Factory is
  paid.

**`ledgerguard/evaluation/model_comparison.py`**

- New `--out` option, default `model_comparison`. It sets the file name of the
  two output files. Without it, a Nemotron run would overwrite the September
  comparison that the README cites. The default keeps the old behaviour.

**`ledgerguard/evaluation/benchmark.py`**

- `nebius` added to the `--provider` help text and to the message printed when
  the run fell back to the offline stub. No logic change.

**`ledgerguard/tests/test_nebius.py`** (new, 4 tests, no network)

- The preset points at Token Factory and a Nemotron model.
- `LEDGERGUARD_MODEL` overrides the model.
- Asking for `nebius` with no key raises an error instead of silently using the
  offline stub, so a "Nemotron" result can never actually be stub output.
- With the HTTP client replaced by a fake, the request goes to the right URL,
  with the key as a bearer token, the Nemotron model id and json_object format,
  and an answer that starts with `<think>...</think>` still parses.

**`run_nemotron_eval.sh`** (new)

- Creates the virtualenv if missing, stops early if `NEBIUS_API_KEY` is not set,
  sets `LEDGERGUARD_REASONING_EFFORT=low` unless you set it yourself (thinking
  tokens count against the 1200 token answer limit; if the host rejects the
  parameter the code drops it and retries), runs the tests, then runs the
  comparison on the frozen holdout with `--providers nebius --out
  nemotron_comparison`.
- At the end it reads the JSON and exits with an error if any investigation
  never reached Nemotron, so an all failed run is not mistaken for a result.

**`.env.example`**, **`README.md`**, **`LICENSE`**

- `.env.example` documents `NEBIUS_API_KEY` and the new chain order.
- README: the hackathon update section with result placeholders, a note in
  Secrets about the new key, and a License section.
- MIT license, copyright 2026 Rajiv Ranganath.

## (c) After you get the key

1. Put the key in `.env` (gitignored), as a new line:

   ```
   NEBIUS_API_KEY=your-key
   ```

2. Optional but worth 10 seconds: confirm the Nemotron model ids exist on your
   account.

   ```bash
   curl -s https://api.tokenfactory.nebius.com/v1/models \
     -H "Authorization: Bearer $(grep ^NEBIUS_API_KEY= .env | cut -d= -f2)" \
     | grep -io '"id": *"[^"]*nemotron[^"]*"'
   ```

   If `nvidia/Nemotron-3_5-Lightning` is not listed, pick a Nemotron id from the
   output and add `LEDGERGUARD_MODEL=<that id>` to `.env`.

3. Run the evaluation:

   ```bash
   ./run_nemotron_eval.sh
   ```

   It prints the table and writes
   `ledgerguard/evaluation/outputs/nemotron_comparison.md` and `.json`. If it
   ends with "Some investigations never reached Nemotron", do not publish the
   numbers; check the key and model id and run it again.

4. Fill the README placeholders from the `providers[0]` entry of
   `nemotron_comparison.json` (or the `nebius:...` row of the `.md` table):

   | Placeholder | JSON field |
   |---|---|
   | `[RESULT PENDING: provider]` | `provider` |
   | `[RESULT PENDING: accuracy]` | `accuracy` (written as a percent in the .md) |
   | `[RESULT PENDING: f3_resolved of f3_total]` | `f3_resolved` of `f3_total` |
   | `[RESULT PENDING: investigator_wanted_to_close_f6 of f6_total]` | `investigator_wanted_to_close_f6` of `f6_total` |
   | `[RESULT PENDING: false_auto_resolutions]` | `false_auto_resolutions` (and `false_auto_resolved_value_inr` if you want the rupee value) |
   | `[RESULT PENDING: invalid_responses, unavailable]` | `invalid_responses`, `unavailable` |

   Copy the numbers exactly. Do not round or restate them.

5. Optional, for the demo video: `LEDGERGUARD_PROVIDER=nebius ./run_demo.sh`.
   This also regenerates `benchmark.md`, `benchmark.json`, `cases.json` and
   `unresolved_exceptions.csv` with Nemotron as the investigator. Those files
   are what the September README numbers cite, so do not commit them. To put
   them back:

   ```bash
   cd ledgerguard/evaluation/outputs
   git checkout -- benchmark.md benchmark.json cases.json unresolved_exceptions.csv
   cd -
   ```

6. Commit the results:

   ```bash
   git add ledgerguard/evaluation/outputs/nemotron_comparison.md \
           ledgerguard/evaluation/outputs/nemotron_comparison.json README.md
   git commit -m "Record the Nemotron evaluation on Nebius Token Factory"
   ```

   Check `git status` first. Never add `.env`, the `.mp4` or the screenshot.
