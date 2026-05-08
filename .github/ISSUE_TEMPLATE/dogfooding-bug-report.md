---
name: Dogfooding bug report (week 1)
about: Report bugs found during your one-week real workflow trial
title: "[dogfood] "
labels: bug, dogfooding
assignees: ""
---

## Trial context

- Day in trial (1-7):
- Real task you were doing:
- Repo type (app/library/monorepo):

## Command and mode

- Command used (`safepush`, `run`, `scan`, etc):
- Dry-run or execute:
- Override used (`yes/no`):
- If override used, reason text:

## What went wrong

Describe the observed bug.

## Risk classification

- [ ] False positive (blocked safe change)
- [ ] False negative (missed risky content)
- [ ] Unsafe git behavior
- [ ] UX confusion / unclear prompt
- [ ] Performance issue
- [ ] Other

## Reproduction steps

1.
2.
3.

## Expected behavior

What outcome did you expect?

## Evidence

- Terminal output:
- Relevant `.safepush-audit.log` lines:
- Sanitized sample file/path if helpful:

## Severity

- [ ] Low
- [ ] Medium
- [ ] High
- [ ] Critical
