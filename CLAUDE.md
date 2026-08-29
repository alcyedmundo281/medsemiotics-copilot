# Claude Code guidance

Follow `AGENTS.md` as the repository-wide engineering and safety contract.

Claude Code may inspect, edit, test, commit, and propose pull requests from a local or hosted
GitHub checkout. It must not place Google OAuth files, API keys, student data, patient data, or
other confidential material in the repository, logs, issues, or pull requests.

Keep LLM reasoning behind the provider-neutral boundary described in
`docs/llm-provider-strategy.md`; never couple an LLM client directly to Calendar publishing.
