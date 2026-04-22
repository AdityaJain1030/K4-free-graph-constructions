#!/usr/bin/env python3
"""Read Claude Code stream-json from stdin, emit readable lines."""
import sys, json

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        e = json.loads(line)
    except json.JSONDecodeError:
        print(line, flush=True)
        continue
    t = e.get("type")
    if t == "assistant":
        for c in e.get("message", {}).get("content", []):
            if c.get("type") == "text":
                txt = c.get("text", "").strip()
                if txt:
                    print(txt, flush=True)
            elif c.get("type") == "tool_use":
                name = c.get("name", "?")
                inp = json.dumps(c.get("input", {}), ensure_ascii=False)
                if len(inp) > 240:
                    inp = inp[:240] + "..."
                print(f"\n[{name}] {inp}", flush=True)
    elif t == "user":
        for c in e.get("message", {}).get("content", []):
            if isinstance(c, dict) and c.get("type") == "tool_result":
                content = c.get("content", "")
                if isinstance(content, list):
                    content = "".join(x.get("text", "") if isinstance(x, dict) else str(x)
                                      for x in content)
                snippet = str(content).strip().replace("\n", " ")
                if len(snippet) > 300:
                    snippet = snippet[:300] + "..."
                if snippet:
                    print(f"  -> {snippet}", flush=True)
    elif t == "result":
        print(f"\n=== END: {e.get('subtype', '?')} ===", flush=True)
    elif t == "system" and e.get("subtype") == "init":
        print(f"[session {e.get('session_id', '')[:8]} started, model={e.get('model', '?')}]", flush=True)
