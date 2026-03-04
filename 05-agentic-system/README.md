# PandasAI Introduction

An interactive guide for using PandasAI with SQL databases and the Semantic Layer. This project demonstrates how to analyze data through natural language using PandasAI, connecting directly to PostgreSQL databases and creating reusable semantic layer configurations.

## Setup

### Prerequisites

- **Python 3.10 or 3.11** (required - Python 3.12 not yet supported by pandasai-sql)
- **Poetry**
- **OpenAI API Key**

### Installation Steps

1. **Install Poetry** (if not already installed):
   
   **Windows (PowerShell)**:
   ```powershell
   (Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | py -
   ```
   
   **macOS/Linux**:
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```
   
   After installation, restart your terminal. If `poetry` command is not found:
   - **Windows**: Add `%APPDATA%\Python\Scripts` to your system PATH
   - **macOS/Linux**: Add `export PATH="$HOME/.local/bin:$PATH"` to your `~/.bashrc` or `~/.zshrc`

2. **Install dependencies**:
   ```bash
   poetry install
   ```
   
   This will install all dependencies with the exact versions specified in `poetry.lock`, ensuring consistency across all environments.

3. **Set up your environment variables**:
   
   **Windows**:
   ```powershell
   copy .env.example .env
   ```
   
   **macOS/Linux**:
   ```bash
   cp .env.example .env
   ```
   
   Then edit `.env` and add your credentials:
   ```
   OPENAI_API_KEY=sk-your-key-here
   DB_HOST=your-database-host
   DB_USER=your-username
   DB_PASS=your-password
   DB_NAME=your-database-name
   DB_PORT=5432
   ```

### Multiple Python Versions?

If you have multiple Python versions installed and want to use a specific one:

```bash
# Tell Poetry which Python to use
poetry env use python3.11  # or python3.10

# Then install dependencies
poetry install
```

Poetry will create a virtual environment with your chosen Python version.

## Usage

### Running the Notebook

1. Open `pandasai_quickstart_guide.ipynb` in Cursor
2. Select the Poetry kernel when prompted (look for `pandasai-introduction-xxxxx-py3.xx`)
3. Run cells sequentially using Shift+Enter

If necessary install the Jupyter extension for Cursor: https://cursor.dev/docs/extension/jupyter

## Project Structure

```
pandas-ai-introduction/
├── quickstart.ipynb         # Interactive tutorial notebook
├── datasets/                # Semantic layer configurations (auto-generated)
├── pyproject.toml          # Dependencies configuration
├── poetry.lock             # Locked dependency versions
├── .env.example            # Environment variables template
└── README.md               # This file
```

**Important**: The `poetry.lock` file is committed to ensure all users get identical, tested dependency versions.