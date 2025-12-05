# Synchronization Client (Local Change Queue)

## Overview

This module (`pokedo/data/sync.py`) implements the client-side logic for our "local-first" synchronization strategy. It ensures that all user actions (creating tasks, catching Pokemon) are first saved locally and then queued for upload to the server. This allows the CLI to work seamlessly offline.

## Core Concepts

1.  **Local-First:** The application always writes to the local SQLite database first.
2.  **Change Queue:** Every significant data modification (Create, Update, Delete) creates a corresponding `Change` record in the local `change` table.
3.  **Push Mechanism:** A separate process (or command) reads unsynced changes from this queue and sends them to the server via HTTP POST.
4.  **Last-Write-Wins:** The server is responsible for resolving conflicts based on timestamps.

## Implementation Details

### The Change Model

The `Change` model (defined in `pokedo/data/sync.py`) tracks atomic operations:

-   `id`: Unique UUID for the change.
-   `entity_id`: ID of the object being changed (e.g., Task UUID).
-   `entity_type`: Type of object (e.g., "task", "pokemon").
-   `action`: The operation type ("CREATE", "UPDATE", "DELETE").
-   `payload`: JSON dictionary containing the data.
-   `timestamp`: When the change occurred (UTC).
-   `synced`: Boolean flag, `False` until successfully pushed.

### Queueing Changes

We use the `queue_change()` function to add records. This should be called immediately after a successful DB commit.

**Example:**

```python
# In a CRUD function
db.add(new_task)
db.commit()

# Queue the sync event
queue_change(
    entity_id=str(new_task.id),
    entity_type="task",
    action="CREATE",
    payload=new_task.dict()
)
```

### Pushing Changes

The `push_changes(server_url)` function handles the upload process:

1.  Selects `limit` rows from `change` where `synced` is `False`, ordered by time.
2.  Constructs a JSON payload containing the batch of changes.
3.  Sends a `POST` request to `{server_url}/sync`.
    -   **Authentication:** Requires a Bearer token (JWT) in the header.
    -   **Library:** Uses `requests` (synchronous) for simplicity in this background task.
4.  If the server responds with 200 OK, the local records are marked as `synced = True`.

## Usage

### Initialization

The sync table must be created in the local DB before use.

```bash
# CLI command
python -m pokedo.data.sync init
```

### Manual Push

You can trigger a sync manually (useful for testing or crontabs).

```bash
# Push to the local dev server
python -m pokedo.data.sync push http://localhost:8000
```

**Note:** The current CLI implementation of `push` in `sync.py` does not yet support passing the auth token as an argument. This is a known limitation for the prototype.

### Testing the Queue

You can manually queue a dummy change to verify the system.

```bash
python -m pokedo.data.sync queue "test-id-1" task CREATE "{\"title\": \"Manual Sync Test\"}"
```

## Future Improvements

-   **Auth Integration:** The CLI `push` command needs to read the stored JWT from the config/session.
-   **Background Daemon:** Ideally, a background thread or separate process would run `push_changes` periodically.
-   **Pull Sync:** We currently only support "Push". "Pulling" updates from other devices is the next major milestone.
