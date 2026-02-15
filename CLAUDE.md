# ClawPet - Development Rules

## After Code Changes Routine

When modifying `server.py` or any source code:

1. Kill existing server process: `pkill -f "python3 server.py"`
2. Restart server: `nohup python3 /data/data/com.termux/files/home/claude-chat/server.py >> /data/data/com.termux/files/home/claude-chat/server.log 2>&1 &`
3. Open Chrome: `am start -a android.intent.action.VIEW -d "http://127.0.0.1:8888"`
4. Commit and push: `git add . && git commit && git push`

Always perform steps 1-3 immediately after any source code change. Step 4 on every fix/feature.
