# ClawPet - Development Rules

## After Code Changes Routine

When modifying `server.py` or any source code:

1. Kill existing server process: `pkill -f "python3 server.py"`
2. Restart server: `nohup python3 /data/data/com.termux/files/home/claude-chat/server.py >> /data/data/com.termux/files/home/claude-chat/server.log 2>&1 &`
3. Open Chrome: `am start -a android.intent.action.VIEW -d "http://127.0.0.1:8888"`
4. Commit and push: `git add . && git commit && git push`

Always perform steps 1-3 immediately after any source code change. Step 4 on every fix/feature.

## Pre-commit Hook (E2E Tests)

Git pre-commit hook runs `test_e2e.py` automatically before every commit.
- Server must be running on port 8888 for tests to pass
- 50 Selenium tests cover: initial state, info modal, toggles, send/response, duplicates, NEW button, speak/stop, poop system, persistence
- If tests fail, commit is blocked
- Run manually: `python3 test_e2e.py`
- Hook location: `.git/hooks/pre-commit`

## Kill Server Properly

Always kill by PID, not just `pkill -f`. The `-9` flag and waiting for port release:
```bash
kill -9 $(pgrep -f "python3 server.py") 2>/dev/null; sleep 3
```
