---
name: run-edge-demo
description: "Launch the edge file watcher demo on sample data to verify that file detection, metadata extraction, and quality checks work correctly."
user-invocable: true
allowed-tools: Bash, Read, Write, Grep
context: fork
---

You are running the edge node demo for Jarvis Mesh.

## Steps

1. Check if sample data exists:
```bash
ls -la tests/fixtures/ 2>/dev/null || echo "No test fixtures found"
```

2. Create a temporary watch directory if needed:
```bash
mkdir -p /tmp/jarvis-edge-demo
```

3. Start the edge watcher in background:
```bash
python3 -m jarvis_mesh.edge.watcher --watch-path /tmp/jarvis-edge-demo --config configs/default.yaml &
WATCHER_PID=$!
echo "Watcher started with PID: $WATCHER_PID"
```

4. Copy sample files to trigger detection:
```bash
# Copy test fixtures or create dummy files
echo '{"test": true}' > /tmp/jarvis-edge-demo/test_session.json
```

5. Wait and check results:
```bash
sleep 3
# Check watcher output / logs
```

6. Stop the watcher:
```bash
kill $WATCHER_PID 2>/dev/null
```

7. Report: what files were detected, what metadata was extracted, what quality checks ran.
