# LLM Engineering

By **[Chase Dovey](https://cdovey.dev/)** · [Average Joes Lab](https://github.com/averagejoeslab)

*The purpose of this repo is to teach the five disciplines of building with language models, each from its primitives.*

A language model does one thing: tokens go in, and it predicts the next one. Everything we build with it is built outward from there, one layer at a time. This repo teaches each layer as its own discipline, in its own module:

| Module | The one idea | Primitives | What you build |
|---|---|---|---|
| [Prompt Engineering](./prompt-engineering/) | `TokensOut = Model(TokensIn)`: a prompt is `TokensIn` | instruction, role, data, examples, format, reasoning, settings | a prompt that turns customer emails into order records |
| [Context Engineering](./context-engineering/) | `TokensIn = Context(everything it could know)` | source, select, place, fit, store, isolate | a help desk that answers from a handbook far bigger than its window |
| [Harness Engineering](./harness-engineering/) | `Agent = Harness(Model)` | input, context, model interface, output, control flow | an agent that fixes a failing test through the shell |
| [Loop Engineering](./loop-engineering/) | `Loop(Agent)`: a run ending isn't the job being done | trigger, check, state, stop | a loop that works through a backlog across many runs |
| [Graph Engineering](./graph-engineering/) | `System = Graph(Agents)` | node, edge, state, router | a graph that takes a feature request through plan, build and review |

## How the modules fit

Each module starts from the previous one's finished result, treated as one black box, and builds one ring further out:

```
┌─ graph ─────────────────────────────────────────────────────┐
│  many agents, connected                                     │
│  ┌─ loop ────────────────────────────────────────────────┐  │
│  │  one agent, run again until the work is done          │  │
│  │  ┌─ harness ───────────────────────────────────────┐  │  │
│  │  │  one agent: a model that can observe and act    │  │  │
│  │  │  ┌─ context ─────────────────────────────────┐  │  │  │
│  │  │  │  everything one call is shown             │  │  │  │
│  │  │  │  ┌─ prompt ────────────────────────────┐  │  │  │  │
│  │  │  │  │  what one call says                 │  │  │  │  │
│  │  │  │  │  ┌─ model ───────────────────────┐  │  │  │  │  │
│  │  │  │  │  │  tokens in ─► next token      │  │  │  │  │  │
│  │  │  │  │  └───────────────────────────────┘  │  │  │  │  │
│  │  │  │  └─────────────────────────────────────┘  │  │  │  │
│  │  │  └───────────────────────────────────────────┘  │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

But every module is **self-contained**: it re-derives what it needs from first principles, ships its own code and its own task, and never depends on another module. Read them in order to see the whole stack, or start with the one you need.

## How each module teaches

Every module is one README that runs end to end, in the same shape:

| Part | What it does |
|---|---|
| **What is it?** | a human intuition first, then the idea from first principles |
| **Primitives** | the few parts it reduces to, in a table |
| **Building it** | one primitive at a time, on one running task: what it is, its code, a real run, and what's still missing |
| **Evaluating it** | tasks with known right answers, checked by what it did, not what it says |
| **Getting it ready for production** | a few questions asked of every primitive, each answer a few marked lines of code |
| **What you built** | the primitives, and how every real system is made of them |

Every step is a complete, runnable Python file that adds one primitive to the last, and every run shown is a real one.

## Setup

You need [uv](https://docs.astral.sh/uv/) to run the code and an [Anthropic API key](https://console.anthropic.com/). Each script declares its own dependencies, so there's nothing to install first:

```bash
export ANTHROPIC_API_KEY=your-key
cd prompt-engineering
```

Each module's README picks up from there. The code uses Claude Sonnet through Anthropic's Python SDK; every file names its model on one line, `MODEL = "claude-sonnet-5-5"`, so it's easy to change.

Some modules run commands on your machine, through the agent they build. Their READMEs say so before you run anything.

## License

The code (the Python files and each module's task files) is under the [MIT License](./LICENSE). The written course (the READMEs) is under [Creative Commons Attribution 4.0](./LICENSE-CC-BY-4.0) (CC BY 4.0): you can share and adapt it, for any purpose, as long as you credit Chase Dovey and link back to this repo.

Copyright © 2026 Chase Dovey.
