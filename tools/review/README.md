tools/review/ — AI-Assisted Code and Specification Review

Two tools for preparing Crowsong contributions for AI-assisted review.

Both follow the same pattern: collect the relevant files, prepend a
rigorous review prompt, and write the result to stdout for pasting into
a chat session.

Directory layout:

    tools/review/
        crowsong-review.py      Code review preparation
        crowsong-speccheck.py   Spec/code alignment review preparation
        README.md               This file

------------------------------------------------------------------------

Why chat, not coding assistant mode

Both tools are designed for use in direct chat sessions with a
foundation model — Claude, ChatGPT, Gemini, or any other capable model —
not in IDE-integrated coding assistant mode.

The distinction matters.

Coding assistant mode (Copilot, Cursor, etc.) optimises for autocomplete
and local suggestions. The model sees a narrow context window around the
cursor. It is good at finishing a function. It is not well suited to
holding the whole Crowsong architecture in mind while evaluating whether
a spec section correctly describes an algorithm spread across several
files.

Direct chat gives you full control over context. You paste exactly what
you want reviewed. The model reads it before responding. You can ask
follow-up questions, challenge findings, request alternative normative
phrasing, or ask for a worked example of a specific algorithm.

The conversation is the review.

This also makes the review reproducible and shareable. The prompt is
committed to the repo. The input files are committed. Anyone can
reproduce the review session by running the tool and pasting into a
fresh chat.

------------------------------------------------------------------------

Multi-model collaboration

One of the most effective review patterns is to run the same buffer
through more than one model and compare the results.

Different models often notice different things. That is not a flaw. It is
a sign of a healthy ecosystem.

Some models are stronger on normative precision. Some are better at
structural suggestions. Some are better at catching terminology drift,
missing examples, or awkward phrasing. These strengths evolve over time.
Do not hard-code assumptions about which model is best at which task.
Test them. Compare them. Use the diversity.

The workflow:

    python tools/review/crowsong-review.py tools/haiku/ | pbcopy

    # Paste into one model -> save findings
    # Paste into another model -> save findings
    # Compare, synthesise, open ISSUE-TRACKER entries

This is not about playing models off against each other. It is about
using more than one reviewer on a complex change.

You can also carry findings across models: take a comment from one
review, paste it into another session, and ask whether the finding is
correct or whether the proposed fix is sound.

The models are collaborators, not oracles.

Practical note: paste the full buffer into a fresh session each time.
Do not rely on conversation history. The review prompt is designed to be
self-contained. Starting fresh ensures the model reads the materials
without prior context colouring its judgement.

------------------------------------------------------------------------

crowsong-review.py -- Code review

Collects source files and prepends the Crowsong code review prompt.
The recipient AI acts as a rigorous code reviewer with full knowledge of
the Crowsong design constraints.

Examples:

    # Review a tool directory
    python tools/review/crowsong-review.py tools/haiku/ | pbcopy

    # Review a single file
    python tools/review/crowsong-review.py tools/haiku/haiku_grammar.py | pbcopy

    # Review all Python in mnemonic tools
    python tools/review/crowsong-review.py tools/mnemonic/ --ext .py | pbcopy

    # Check scope before pasting
    python tools/review/crowsong-review.py tools/ --dry-run

    # Just the prompt (to read or customise)
    python tools/review/crowsong-review.py --prompt-only

    # Linux clipboard
    python tools/review/crowsong-review.py tools/haiku/ | xclip -selection clipboard

The review prompt covers:
correctness, Python 2.7/3.x compatibility, security considerations
(prompt injection, Von Neumann boundary, CCL non-cryptographic caveat),
pipeline composability, artifact format compliance, Crowsong conventions,
README and documentation quality, test coverage, style, and maintainability.

Output format:
severity-rated findings (critical / high / medium / low / nit) with file
and line references, plus suggested ISSUE-TRACKER entries for
non-blocking issues.

------------------------------------------------------------------------

crowsong-speccheck.py -- Spec/code alignment review

Collects draft specifications and reference implementation, structured
in two explicit sections. The recipient AI acts as an IETF-style
standards reviewer whose job is to tighten the specifications so they
describe exactly what the code actually does.

Examples:

    # Full review — all drafts against all tools
    python tools/review/crowsong-speccheck.py | pbcopy

    # Check scope first
    python tools/review/crowsong-speccheck.py --dry-run

    # Specific spec against specific code
    python tools/review/crowsong-speccheck.py \
        --code tools/mnemonic/ \
        --drafts drafts/ | pbcopy

    # Just the prompt
    python tools/review/crowsong-speccheck.py --prompt-only

The code is the ground truth.
The spec must describe what the code does precisely enough that an
independent implementer can produce a conformant result without reading
the source.

The review prompt covers:
spec-to-implementation alignment (gaps, contradictions,
underspecification, over-specification), normative precision
(MUST/SHOULD/MAY), algorithm descriptions, RSRC block schema,
interoperability requirements, RFC-style structure, language, and style.

Documentation and graphics recommendations are explicitly requested.
The reviewer identifies places where a diagram, worked example, table,
or decision tree would prevent a class of implementation error, with
placement suggestions and reasoning.

------------------------------------------------------------------------

Options reference

Both tools share the same structure:

    --dry-run           print file list and char count without concatenating
    --prompt-only       print the review prompt and exit
    --no-prompt         omit the review prompt; output files only
    --max-kb N          skip files larger than N KB (default: 500)
    --exclude PAT       directory/file patterns to exclude

crowsong-review.py only:
    --ext EXT           file extensions to include

crowsong-speccheck.py only:
    --ext-code EXT      code file extensions
    --ext-drafts EXT    draft file extensions
    --code PATH         path to reference implementation
    --drafts PATH       path to draft specifications

Defaults:

    extensions (review):  .py .sh .md .txt
    extensions (code):    .py .sh
    extensions (drafts):  .txt .md
    code path:            tools/
    drafts path:          drafts/

    excludes: __pycache__ .git .mypy_cache .tox node_modules
              .eggs dist build *.pyc *.pyo *.egg-info

------------------------------------------------------------------------

Workflow for contributors

Before opening a PR:

    # 1. Check scope
    python tools/review/crowsong-review.py <your-tool-dir>/ --dry-run

    # 2. Run code review
    python tools/review/crowsong-review.py <your-tool-dir>/ | pbcopy
    # Paste into a fresh chat session
    # Fix blocking issues

    # 3. If you have touched specs
    python tools/review/crowsong-speccheck.py \
        --code <your-tool-dir>/ \
        --drafts drafts/ | pbcopy
    # Paste into a fresh chat session

    # 4. Open ISSUE-TRACKER entries for non-blocking findings
    # 5. Open PR

For spec authors:

Run crowsong-speccheck.py after every significant implementation change.
The spec drifts from the code faster than you think. The tool is cheap
to run. Use it.

------------------------------------------------------------------------

Compatibility

Python 2.7+ / 3.x. No external dependencies.

------------------------------------------------------------------------

A note on the review prompts

The review prompts are normative artifacts. They encode the Crowsong
project's expectations for contribution quality.

If a review dimension is missing, or if there is a question that should
be asked every time, open a PR and update the prompt.

The prompt is the spec for the review.

Signal survives if the implementations are correct.
The implementations are correct if the specs are exact.
The specs are exact if the review is rigorous.
