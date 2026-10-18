# a2a-stream-tax

**Measure the token tax of A2A streaming (SSE) sessions. Dumb math, honest numbers, zero dependencies.**

[![Tests](https://img.shields.io/badge/tests-12%20passed-brightgreen)]() [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)]()

Companion to [a2a-tax](https://github.com/ZidoCode/a2a-tax) (the polling tax). This one measures the **stream**.

A2A's `message/stream` emits a JSON-RPC `StatusUpdateEvent` on every state change and an `ArtifactEvent` on every chunk. Each event re-ships the full envelope: jsonrpc frame, task id, context id, status snapshot, timestamps. A chatty agent streaming a long task pushes most of its tokens through **status chatter** — events the client barely reads — not through the answer itself.

Nobody measures this. a2a-stream-tax does.

## Install

```bash
pip install a2a-stream-tax   # or: copy a2a_stream_tax.py + a2a_tax.py, two files
```

## Usage

```bash
$ a2a-stream-tax measure stream.jsonl
events: 35
  status     (  30 ev)  :    2,270 tok
  artifact   (   5 ev)  :      310 tok
  of which envelope overhead:    1,535 tok
  TOTAL streamed           :    2,580 tok  (~$0.0077)

$ a2a-stream-tax report stream.jsonl

  TOTAL streamed           :    2,580 tok  (~$0.0077)
  with the fix (coalesce status + trim envelope):
    after fix              :      325 tok  (~$0.0010)
    savings                :    2,255 tok  (87%)

$ a2a-stream-tax simulate https://agent.example.com --updates 30
card_tokens           : 391
per_status_tokens     : 70
status_share_pct      : 75.5   # status events' share of the bill, not envelope
total                 : 2,781
```

## Stream format

One JSON event per line, as emitted by `message/stream`:

```
{"jsonrpc":"2.0","id":1,"result":{"kind":"status-update","taskId":"t1","contextId":"c1","status":{"state":"working"},"final":false}}
{"jsonrpc":"2.0","id":1,"result":{"kind":"artifact-update","taskId":"t1","artifact":{...}}}
```

Record one with `curl -N .../message/stream > stream.jsonl` (jq -c each line), or any A2A client that logs events. Half-written last lines (stream cut mid-write) are skipped with a note, not a crash.

## The fix

1. **Coalesce status events** — ship only state transitions (`working → completed`), not every heartbeat
2. **Trim the envelope** — don't re-ship the task snapshot with every event
3. **Stream artifacts without metadata re-shipping** — chunk id once, stream the bytes

## Honest numbers

Token counts are deterministic estimates (`chars/4`). Two runs of the same stream produce identical numbers. Prices are input-token rates you supply (`--price-per-mtok`, default $3.00). The point is the **shape**: envelope overhead regularly dwarfs payload — 90% of a status-chatty stream is metadata nobody reads.

MIT license.
