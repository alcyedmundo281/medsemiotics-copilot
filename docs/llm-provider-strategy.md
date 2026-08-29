# Mixed LLM and cloud-agent strategy

MedSemiotics uses two separate kinds of AI capability. They must not be confused.

## 1. Cloud development agents

Codex cloud and Claude Code on the web may work from isolated hosted checkouts of the GitHub
repository. They are engineering operators: they inspect code, create branches, run quality
gates, and propose changes. Repository access does not grant access to the local Google OAuth
files or runtime secrets.

`AGENTS.md` is the shared repository contract. `CLAUDE.md` directs Claude Code to that same
contract so local and cloud agents preserve the same safety boundaries.

## 2. Product reasoning providers

The application may later use OpenAI and Anthropic APIs through a provider-neutral interface.
The deterministic domain remains authoritative:

```text
Syllabus + teaching log + effective schedule + approved guide
                            |
                            v
                  deterministic context
                            |
                optional LLM draft enrichment
                    /                 \
              OpenAI API         Anthropic API
                    \                 /
                     structured draft
                            |
                   human review gate
                            |
               separately authorized ACT
```

Provider selection must be configuration, not domain logic. A future runtime adapter should
accept a provider, model, bounded input, structured output schema, timeout, and token budget.
It should return provenance containing provider, model, request identifier, timestamp, and
prompt/schema version. Provider failure must fail closed to deterministic drafting; it must not
trigger an external action.

Suggested environment variables for that future adapter are:

```text
MEDSEMIOTICS_LLM_PROVIDER=openai|anthropic|deterministic
MEDSEMIOTICS_OPENAI_MODEL=<configured model>
MEDSEMIOTICS_ANTHROPIC_MODEL=<configured model>
OPENAI_API_KEY=<secret>
ANTHROPIC_API_KEY=<secret>
```

Keys belong only in the runtime secret store or ignored local `.env`. Cloud development-agent
subscriptions and product API billing/credentials are independent boundaries.

## Safety invariants

- No student-identifiable data or protected health information is sent to an LLM by default.
- Clinical claims require traceable, reviewed source material.
- An LLM may recommend or draft; it cannot directly call a Calendar writer.
- Calendar publication remains one session at a time with named approval and ownership metadata.
- No provider fallback may silently broaden permissions or data disclosure.
