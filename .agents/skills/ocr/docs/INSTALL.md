# Install and harness setup

The only hard requirement is [uv](https://docs.astral.sh/uv/): it provides `uvx` and
downloads a compatible Python on first run. The tool is the same Python package on every
surface; harnesses differ only in where the skill files go.

Two facts that recur:

- The **distribution** is `ocr-skill`; the **command** is `ocr`. A second console script
  named `ocr-skill` is installed too, so `uvx ocr-skill <cmd>` resolves with no `--from`
  once the package is published to an index.
- **Not on PyPI yet.** Until it is, every install route uses the git URL. Once published,
  drop `--from git+...` and plain `uvx ocr-skill ...` works.

There is **no MCP server**. Agents drive the `ocr` CLI through their own shell; the skill
file tells them when and how. Prefer `ocr init --quick` once per session if you are unsure
the engine is ready.

**Recommended real OCR:** Vulkan llama.cpp Docker (`docker/`) + `OCR_BACKEND=llamacpp`.
Optional torch path: `deepseek` extra. `OCR_BACKEND=mock` is for tests only.

## Route summary

| You want | Do this |
|---|---|
| Run it once, no install | `uvx --from git+https://github.com/hec-ovi/ocr-skill ocr doctor` |
| Skill in any Agent Skills CLI | `npx skills add hec-ovi/ocr-skill` |
| Skill in noob / Grok `/skills` | `/skills add hec-ovi/ocr-skill` |
| Claude Code plugin | `/plugin marketplace add hec-ovi/ocr-skill` then `/plugin install ocr@ocr-skill` |
| Codex plugin | `codex plugin marketplace add hec-ovi/ocr-skill` |
| Develop on it | `git clone ...` then `uv sync` |

## Why root `SKILL.md` exists

Harnesses that implement the open skills registry (and noob's `/skills add`) look for:

1. `SKILL.md` at the **repo root**, or
2. exactly one **immediate** subdirectory that contains `SKILL.md`

A nested path like `skills/ocr/SKILL.md` alone is enough for `npx skills add` (it walks
the `skills/` container), but **not** for noob-style installers. This repo keeps identical
copies:

| Path | Role |
|---|---|
| `SKILL.md` + `references/` | Root discovery (noob, clone-as-skill) |
| `skills/ocr/` | `npx skills add` layout |
| `plugins/ocr/skills/ocr/` | Claude plugin subtree |
| `plugins/ocr-codex/skills/ocr/` | Codex plugin subtree |

Edit only `skills/ocr/`, then:

```bash
python3 scripts/sync-skill-copies.py
```

## CLI, no install

```bash
uvx --from git+https://github.com/hec-ovi/ocr-skill ocr doctor --quick
uvx --from git+https://github.com/hec-ovi/ocr-skill ocr extract ./scan.png --json
```

`uvx` caches the build, so the second run is fast. Pin a ref with `@v0.3.0` or `@<sha>` on
the git URL for reproducibility. To put `ocr` on PATH permanently:

```bash
uv tool install git+https://github.com/hec-ovi/ocr-skill
ocr doctor --quick
```

For real OCR (Vulkan, recommended):

```bash
# 1) CLI on PATH (above)
# 2) GGUF + mmproj under MODELS_DIR (see docker/README.md)
# 3) server
cp docker/.env.example docker/.env
docker compose -f docker/docker-compose.yml --env-file docker/.env up -d
export OCR_BACKEND=llamacpp
export OCR_LLAMA_URL=http://127.0.0.1:8090
ocr doctor
ocr extract ./scan.png --json
```

Optional torch path: `uv tool install 'git+https://github.com/hec-ovi/ocr-skill[deepseek]'`
and `OCR_BACKEND=deepseek`.

## As an agent skill (`npx skills add`)

The [`skills`](https://www.npmjs.com/package/skills) CLI installs `skills/ocr/` into every
agent it detects (Claude Code, Codex, OpenCode, Cursor, Gemini, Grok Build, and others).

```bash
npx skills add hec-ovi/ocr-skill                 # all detected agents, project scope
npx skills add hec-ovi/ocr-skill -g              # global (your user dir)
npx skills add hec-ovi/ocr-skill -a claude-code -a codex -s ocr
npx skills add hec-ovi/ocr-skill --list
npx skills add hec-ovi/ocr-skill --copy -y       # copy instead of symlink (e.g. Windows)
```

The skill shells out to the `ocr` CLI. Install that too (`uv tool install` above) or use the
`uvx --from git+...` forms documented in `SKILL.md`.

## noob / `/skills add`

```text
/skills add hec-ovi/ocr-skill
```

Clones the repo, finds root `SKILL.md`, copies into `.noob/skills/ocr`. Also works with a
local path:

```text
/skills add /path/to/ocr-skill
```

The pack includes `./ocr` → `dist/ocr` (bundled binary). Agent call:

```bash
.noob/skills/ocr/ocr extract /abs/path/to/file.pdf --json
```

No pip, no uv, no venv. If the binary is missing, reinstall the skill pack.

## Claude Code

### Plugin

```text
/plugin marketplace add hec-ovi/ocr-skill
/plugin install ocr@ocr-skill
/reload-plugins
```

`.claude-plugin/marketplace.json` points at `./plugins/ocr` (a directory that contains
`.claude-plugin/plugin.json` and `skills/ocr/SKILL.md`).

### Manual

`npx skills add` above, or copy/symlink `skills/ocr` into `~/.claude/skills/ocr`.
CLI: `uv tool install` above.

## Codex CLI

```bash
codex plugin marketplace add hec-ovi/ocr-skill
# or
npx skills add hec-ovi/ocr-skill -a codex
uv tool install git+https://github.com/hec-ovi/ocr-skill
```

Codex plugin metadata: `.agents/plugins/marketplace.json` and
`plugins/ocr-codex/.codex-plugin/plugin.json`. Slash command: `/ocr <path>`.

## Grok Build and other Agent Skills hosts

`npx skills add hec-ovi/ocr-skill` installs into detected hosts (including Grok Build when
present). Or place `skills/ocr` under your host's skills directory. The body of `SKILL.md`
is host-agnostic: shell out to `ocr`.

## Develop from a clone

```bash
git clone git@github.com:hec-ovi/ocr-skill.git
cd ocr-skill
uv sync
OCR_BACKEND=mock uv run pytest
OCR_BACKEND=mock uv run ocr extract ./some.png --json
python3 scripts/sync-skill-copies.py
```

## First session checklist

1. `ocr doctor --quick --json` (or `ocr init --quick --json`)
2. If `engine_llamacpp` is not ok: start `docker/` stack and set `OCR_BACKEND=llamacpp`
3. `ocr extract <abs-path> --json`
4. If `has_more`: `ocr open <handle> --page 2 --json`
