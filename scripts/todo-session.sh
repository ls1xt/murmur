#!/usr/bin/env bash
# todo-session.sh
#
# Starts (or attaches to) a tmux session named "todo" with Claude Code
# running in note-taking mode. Murmur can inject into this session via:
#   inject_to: "tmux:todo:0.0"  (Ctrl+Cmd+T)
#
# Each dictated utterance arrives as a new line + Enter, so Claude Code
# receives it as a submitted message and can act on it immediately.
#
# Usage:
#   ./scripts/todo-session.sh          # start/attach
#   ./scripts/todo-session.sh --detach # start in background, don't attach

SESSION="todo"
DETACH=false
[[ "$1" == "--detach" ]] && DETACH=true

# System prompt that puts Claude Code in todo-capture mode
SYSTEM_PROMPT='You are a silent mental todo log. The user dictates notes, tasks, and reminders by voice. Each message is a raw speech-to-text transcription and may contain errors, filler words, or odd phrasing — interpret charitably and extract the intent.

For every message, append exactly one line to TODO.md in the current directory:

  YYYY-MM-DD HH:MM  [keyword1, keyword2]  <cleaned up todo text>

Rules:
- Date/time is the current local time at the moment of capture
- 1–3 lowercase keywords that categorize the todo (e.g. work, health, code, call, buy, read)
- Todo text is one concise sentence, cleaned up from the transcription — fix grammar, remove filler words ("um", "uh", "like"), correct obvious transcription errors based on context
- If a message contains multiple distinct todos, write one line per todo
- Never respond with any text — just silently append to TODO.md and stop
- Never ask for clarification — make a best guess and write it'

if tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "Session '$SESSION' already exists."
else
    echo "Creating tmux session '$SESSION'..."
    tmux new-session -d -s "$SESSION" -x 220 -y 50

    # Give the shell a moment to settle
    sleep 0.3

    # Start Claude Code with the todo system prompt
    tmux send-keys -t "$SESSION:0.0" \
        "claude --system-prompt '$SYSTEM_PROMPT'" \
        Enter

    echo "Claude Code started in session '$SESSION'."
    echo "Murmur binding: Ctrl+Cmd+T → inject_to: tmux:todo:0.0"
fi

if $DETACH; then
    echo "Running in background. Attach with: tmux attach -t $SESSION"
else
    tmux attach -t "$SESSION"
fi
