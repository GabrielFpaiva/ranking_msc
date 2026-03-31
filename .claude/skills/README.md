# Claude Skills — ranking_msc

Skills (slash commands) for developing ranking_msc.

## Available Skills

| Skill | Description | When to Use |
|-------|-------------|-------------|
| `/new-rule` | Implement R<NNN> validation rule | Adding any rule from R001–R070 catalogue |
| `/test` | Write pytest tests | Adding tests for any module |
| `/commit` | Create F<N>-XX git commit | Ready to commit changes |
| `/schema-column` | Add column to schemas.py | New CSV column or output column |
| `/ref-table` | Add reference table loader | New CSV in ref/ needed by rules |

## Workflow

```
Feature: Implement rule R082
    ↓
Check if new columns needed? → /schema-column
Check if ref tables needed? → /ref-table
    ↓
/new-rule R082
    ↓
/test
    ↓
(review: agent code-reviewer)
    ↓
/commit
```

## Skill File Structure

Each skill is a directory with a SKILL.md:

```
.claude/skills/
├── new-rule/SKILL.md
├── test/SKILL.md
├── commit/SKILL.md
├── schema-column/SKILL.md
└── ref-table/SKILL.md
```

## References

- `CLAUDE.md §4` — Implementation patterns
- `CLAUDE.md §5` — Test patterns
- `CLAUDE.md §6` — Git workflow
- `CLAUDE.md §10` — Pre-completion checklist
