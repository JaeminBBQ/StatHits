# Needs the Human

Items Claude needs from the user. Claude adds items; the user answers inline or in chat.

## Open
- [ ] **T006: visual review of the site.** A server is running on your real data; restart it with `uv run didyouhit serve --port 8765` if it's gone.
  - http://localhost:8765/weeks/2026-09-07 (a past week with your real numbers; the best page to judge)
  - http://localhost:8765/ (this week; empty, since your last Arena game was Sep 9)
  - http://localhost:8765/weeks, http://localhost:8765/members/1, http://localhost:8765/join (shows "closed", since no invite code is set)
  - Check these, on desktop **and** phone width (DevTools → device toolbar, ~375px):
    1. Do the big numbers read as the hero? Anything cramped or overflowing?
    2. Is the section order right (Big numbers → Damage & utility → Per minute → Totals)?
    3. Colors, contrast, overall vibe: does it feel like "didyouhit"?
    4. Member page: is the history table usable on a phone?
    5. Anything you'd add, remove or reword?
  - Reply in chat with notes or screenshots, and Claude will turn them into T007.
- [ ] **Register didyouhit.gg** when you're ready. `whois` returned "NOT FOUND" on 2026-09-28, which suggests it's unregistered; confirm at a registrar. Not needed until deploy (T008).

## Done
- [x] Phase 1 run with a dev key (2026-09-27): Mayhem is absent from the API; Arena works.
- [x] App name: **didyouhit.gg** (2026-09-28).
- [x] DeepSeek runs in Claude Code (loads CLAUDE.md, which redirects it to DEEPSEEK.md).
- [x] Git: the user runs commits; Claude says when and gives the command.
