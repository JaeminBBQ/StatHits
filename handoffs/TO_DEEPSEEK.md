# To DeepSeek

**Current tasks, in order:**
1. **T002a**: fix the ingestion cursor and match-level 403 handling. Spec: `handoffs/tasks/T002a-ingest-cursor-and-403-fix.md`
2. **T003**: week windows and weekly boards. Spec: `handoffs/tasks/T003-weeks-and-boards.md`

Do T002a first; T003's tests assume the fixed ingestion. Write a separate report for each (`reports/T002a-report.md`, `reports/T003-report.md`), then **one** `TO_CLAUDE.md` update and **one** Discord notification after both are done. If T002a gets blocked, stop there: update `TO_CLAUDE.md` and notify with `--kind blocked`.

## Feedback on T002
Solid work: clean client, good error types, and the secret-hygiene tests are exactly right. Claude's review found two bugs the tests didn't cover (the cursor advancing past failed matches, and one private match's 403 aborting everything). Both are explained in T002a, which also answers your four questions.
