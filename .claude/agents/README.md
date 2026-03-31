# Claude Agents — ranking_msc

Specialized agents for ranking_msc development work.

## Available Agents

| Agent | Description | Primary Skills |
|-------|-------------|----------------|
| `rule-implementer` | Implements R<NNN> validation rules end-to-end | `/new-rule`, `/test`, `/commit` |
| `code-reviewer` | Reviews code against CLAUDE.md conventions | (checklist-based) |

## When to Use Agents vs Skills

- **Skills** = step-by-step recipe for a specific action
- **Agents** = autonomous role that orchestrates skills to complete a full task

Use the `rule-implementer` agent when you want it to implement a complete rule (read spec, write code, write tests, commit) without step-by-step guidance. Use `/new-rule` directly when you want to follow each step yourself.

## Invocation

Agents are invoked via the Agent tool:

```
Agent({
  subagent_type: "rule-implementer",
  prompt: "Implement rule R082 — debit must equal credit at year-end closing. Use columns debito and credito from schemas.py.",
})
```

## References

- `.claude/skills/README.md` — Available skills
- `CLAUDE.md §4` — Implementation patterns
- `CLAUDE.md §10` — Pre-completion checklist
