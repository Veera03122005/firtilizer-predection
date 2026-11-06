# 12. MCP Connection (development-time, Antigravity)

How to connect Model Context Protocol (MCP) servers to the Antigravity agent so it can inspect the SQLite database, read reference documentation, and work with GitHub while building this project. The running app does **not** use MCP; this is developer tooling only.

> Antigravity's MCP configuration has changed across releases. The paths and keys below follow a May 2026 write-up of the Antigravity IDE/CLI setup (see Sources). If your version differs, use the IDE's MCP settings screen and keep the same server definitions.

---

## 12.1 Why MCP here

| Server | What the agent gains | Used in phases |
| --- | --- | --- |
| SQLite | Query `instance/app.db` to verify saved predictions, chats and cascades | 2, 3, 4, 8 |
| Fetch | Read live docs (google-genai SDK, Open-Meteo, fpdf2) instead of guessing APIs | 3, 6, 7 |
| GitHub | Read issues/PRs, create a PR for the v2 branch | 8 |
| Filesystem (optional) | Read source PDFs/notes kept outside the repo when drafting knowledge-base files | 3 |

The agent already has read/write access to the open workspace, so a filesystem server is only needed for folders outside it.

## 12.2 Prerequisites

| Tool | Needed for | Check |
| --- | --- | --- |
| `uv` (provides `uvx`) | Python-based servers (SQLite, Fetch) | `uvx --version` |
| Node.js 18+ (provides `npx`) | Filesystem server | `npx --version` |
| GitHub fine-grained personal access token | GitHub server | Settings → Developer settings → Fine-grained tokens |

Install uv: `pip install uv` (or the official installer).

## 12.3 Configuration file

| OS | Path |
| --- | --- |
| macOS / Linux | `~/.gemini/config/mcp_config.json` |
| Windows | `%USERPROFILE%\.gemini\config\mcp_config.json` |

Format rules:

- Top-level object `mcpServers`; each key is a server name.
- Local (stdio) servers: `command`, `args`, optional `env`.
- Remote servers: `serverUrl` (not the older `httpUrl`), optional `headers`.
- `"disabled": true` turns a server off without deleting it.
- Plain JSON: no comments, no trailing commas.
- Reported gotcha: values passed through `env` may not reach the server in Antigravity; if a server can't authenticate, pass the token in `headers` (remote) or `args`.

## 12.4 Recommended configuration

Replace `ABSOLUTE_PATH_TO_REPO` and the token. Use absolute paths; `~` is not expanded inside `args`.

```json
{
  "mcpServers": {
    "fertilizer-sqlite": {
      "command": "uvx",
      "args": ["mcp-server-sqlite", "--db-path", "ABSOLUTE_PATH_TO_REPO/instance/app.db"]
    },
    "fetch": {
      "command": "uvx",
      "args": ["mcp-server-fetch"]
    },
    "github": {
      "serverUrl": "https://api.githubcopilot.com/mcp/",
      "headers": {
        "Authorization": "Bearer YOUR_FINE_GRAINED_PAT"
      }
    },
    "kb-sources": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "ABSOLUTE_PATH_TO/agronomy-sources"],
      "disabled": true
    }
  }
}
```

Windows path example: `"C:/Users/<you>/projects/fertilizer-advisor/instance/app.db"` (forward slashes work and avoid escaping).

## 12.5 Server details

### 12.5.1 SQLite (`fertilizer-sqlite`)

- Exposes tools to list tables, describe schema, and run SQL.
- The database must exist first: run `flask --app app init-db`.
- The server includes write tools. Point it at a copy when you only want inspection: `copy instance\app.db instance\app_inspect.db` and use that path.
- Useful agent prompts:
  - "Using the fertilizer-sqlite MCP, describe all tables and compare them with docs/04-DATABASE.md. List any column mismatches."
  - "Show the last 5 predictions with fertilizer, confidence and total_cost."
  - "Verify that deleting prediction 3 removed its chat_messages (foreign keys on)."

### 12.5.2 Fetch (`fetch`)

- Fetches a URL and returns readable text.
- Useful prompts:
  - "Fetch https://googleapis.github.io/python-genai/ and confirm the current way to call embed_content with task_type and output_dimensionality."
  - "Fetch the Open-Meteo forecast API docs and confirm the parameter names for current temperature and relative humidity."
- Only fetch documentation sites; never paste secrets into prompts that trigger fetches.

### 12.5.3 GitHub (`github`)

- GitHub's hosted MCP server; authenticate with a fine-grained PAT.
- Least privilege: limit the token to your fork only, with Contents read/write and Pull requests read/write; set an expiry of 7 days.
- Useful prompts:
  - "Create a pull request from v2-advisor to main titled 'v2: Smart Fertilizer Advisor' with a summary of the phases completed."
  - "List open issues on my fork."

### 12.5.4 Filesystem (`kb-sources`, optional)

- Enable (`"disabled": false`) only when you keep agronomy reference PDFs/notes outside the repo.
- Grant access to that single folder, never your home directory.
- Prompt: "Read the files in kb-sources and draft knowledge_base/crops/maize.md following the front-matter format in docs/10-FEATURE-DEVELOPMENT.md §10.4.1. Mark any number you could not find in the sources with (VERIFY)."

## 12.6 Verify the connection

1. Save `mcp_config.json` and restart Antigravity (or reload the agent).
2. Ask the agent: "What MCP servers do we have?" It should list `fertilizer-sqlite`, `fetch` and `github`.
3. Ask: "Use fertilizer-sqlite to list tables." Expect `users`, `predictions`, `chat_messages`, `contact_messages`.

## 12.7 Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Server not listed | JSON syntax error (comment or trailing comma) | Validate with `python -m json.tool mcp_config.json` |
| `uvx: command not found` | uv not installed or not on PATH | `pip install uv`; restart the IDE so PATH refreshes |
| SQLite server says "no such table" | Wrong path or DB not initialised | Use the absolute path; run `init-db` |
| GitHub 401 | Token missing/expired, or passed via `env` | Put it in `headers`; regenerate the token |
| `npx` hangs on first run | Downloading the package | Wait; or run the npx command once in a terminal |
| Agent ignores MCP tools | It didn't consider them relevant | Name the server explicitly in the prompt |

## 12.8 Security rules for MCP

- `mcp_config.json` lives in your user profile, never in the repo; it may contain tokens.
- Use expiring, repo-scoped tokens.
- Prefer read-only access (DB copy for SQLite).
- Review every write action the agent proposes through MCP (SQL `DELETE`/`UPDATE`, PR creation) before approving.

## 12.9 Sources

- [Configuring MCP servers and skills for Antigravity CLI and IDE (Google Cloud Community, May 2026)](https://medium.com/google-cloud/configuring-mcp-servers-and-skills-for-antigravity-cli-and-ide-a938c7eebb78)
- [Google Developer Knowledge MCP server in Antigravity (codelab)](https://codelabs.developers.google.com/developer-knowledge-mcp-antigravity)
