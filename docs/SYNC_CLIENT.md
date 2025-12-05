# Sync Client (Local change queue)

## Overview

This module provides a local `changes` queue and a simple push client to send unsynced changes to the Pokedo server `/sync` endpoint.

## Files added

- `pokedo/data/sync.py` — Change model, queueing helpers, push client, and CLI entrypoints.

## Quick usage

Initialize the table (once):

```cmd
python -m pokedo.data.sync init
```

Queue a change:

```cmd
python -m pokedo.data.sync queue "task-123" task CREATE "{\"title\": \"Write doc\"}"
```

Push to server:

```cmd
# Requires valid JWT token (not yet implemented in CLI push command)
python -m pokedo.data.sync push http://localhost:8000
```

## Authentication

The server now requires authentication for the `/sync` endpoint.
1. Obtain a token via `POST /token`
2. Send token in `Authorization: Bearer <token>` header

## Notes

- By default the module uses `sqlite:///pokedo.db`. Set `POKEDO_DATABASE_URL` env var to change.
- The push logic is simple: POST a batch to `/sync` and mark local rows as `synced` on success. It uses a Last-Write-Wins style approach at server-side (server must implement LWW).
