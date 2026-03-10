# Contributing

## Setup

1. Clone the repository:

   ```bash
   git clone https://github.com/willianpaixao/polar-running-index.git
   cd polar-running-index
   ```

2. Install dependencies with [uv](https://docs.astral.sh/uv/):

   ```bash
   uv sync
   ```

   This installs the project in editable mode along with dev dependencies
   (pytest, ruff).

## Development workflow

### Running tests

```bash
uv run pytest
```

For verbose output:

```bash
uv run pytest -v
```

### Linting and formatting

This project uses [Ruff](https://docs.astral.sh/ruff/) for both linting and
formatting. Run both checks before submitting changes:

```bash
uv run ruff check .
uv run ruff format --check .
```

To auto-fix lint issues:

```bash
uv run ruff check --fix .
```

To format code:

```bash
uv run ruff format .
```

### Full check before committing

```bash
uv run ruff check . && uv run ruff format --check . && uv run pytest
```
