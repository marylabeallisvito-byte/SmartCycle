# Contributing to SmartCycle

Thanks for your interest in contributing! SmartCycle is an AI-native financial intelligence platform, and we welcome contributions from developers, financial professionals, and AI enthusiasts.

## Getting Started

1. **Fork** the repository
2. **Clone** your fork: `git clone https://github.com/YOUR_USERNAME/SmartCycle.git`
3. **Set up** the dev environment — see [README.md](README.md#-quick-start)
4. **Create a branch**: `git checkout -b feat/your-feature-name`

## Development Workflow

### Backend (Python)

```bash
cd backend
PYTHONPATH=. python server_tornado.py    # Start the API server
PYTHONPATH=. pytest -v                    # Run tests
ruff check app/ tests/                    # Lint
mypy app/ --ignore-missing-imports        # Type check
```

### Frontend (TypeScript)

```bash
cd frontend
npm install --legacy-peer-deps
npm run dev          # Start dev server (port 3000)
npm run lint         # ESLint
npm run typecheck    # TypeScript type check
npm run build        # Production build
```

## Commit Convention

We follow [Conventional Commits](https://www.conventionalcommits.org/):

| Prefix     | Use for                                      |
|------------|----------------------------------------------|
| `feat:`    | New feature                                  |
| `fix:`     | Bug fix                                      |
| `docs:`    | Documentation only                           |
| `refactor:`| Code change that neither fixes nor adds      |
| `test:`    | Adding or updating tests                     |
| `chore:`   | Tooling, CI, dependencies                    |
| `style:`   | Formatting, whitespace (not logic)           |

## Pull Request Guidelines

- Keep PRs focused — one feature or fix per PR
- Update docs if your change affects user-facing behavior
- Add tests for new functionality
- Ensure CI passes (`ruff`, `mypy`, `pytest` for backend; `lint`, `typecheck`, `build` for frontend)
- Link related issues in the PR description

## Architecture Principles

Before contributing, review the architectural principles in [docs/architecture.md](docs/architecture.md):

1. **Separation of Computation and Narrative** — Tools fetch data; the LLM generates text. Never mix them in the same node.
2. **Compliance is Adversarial** — The Compliance Gatekeeper is a hard gate. All AI-generated financial text must pass a 3-pass screening.
3. **Graceful Degradation** — Every component works without optional dependencies (LangGraph, akshare, yfinance).

## Code Style

- **Python**: Follow [PEP 8](https://peps.python.org/pep-0008/). We use `ruff` for linting and `mypy` for type checking.
- **TypeScript**: Strict mode enabled. Follow the patterns in existing components. Use `tailwind-merge` + `clsx` via the `cn()` utility for styling.
- **Comments**: Write comments for "why", not "what". The code should be self-documenting for the latter.

## Questions?

Open a [GitHub Discussion](https://github.com/marylabeallisvito-byte/SmartCycle/discussions) or join the conversation in Issues.

---

Thank you for helping build the future of intelligent wealth management.
