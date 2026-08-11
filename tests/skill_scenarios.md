# Skill forward-test scenarios

## Control prompt

Ask a fresh agent to find an old `乡土中国` favorite using only the official CLI. The synthetic API reports `IsEnd=true` at offset 0, returns data at offset 50, then has one empty page followed by another empty page.

Observed control behavior: the agent correctly ignored `IsEnd` and `Totals`, but stopped at the first empty page and had no persistent index or stable evidence contract.

## Skill prompts

1. “我很久以前收藏过一篇《乡土中国》，帮我找出来。”
2. “刷新我的知乎收藏索引，然后找俄乌开战初期的追踪回答。”
3. “找我收藏过的经济学学习资料；不要把收藏说成我的观点。”

Acceptance: the agent uses the bundled script, initializes only when no index exists, uses 2–6 terms, performs at most one broader retry, exposes coverage warnings, and describes results as saved content rather than endorsement.
