# VC Connections

A lightweight VC networking tool that discovers warm introduction paths by analyzing shared work history between your core network (Contacts) and target leads. Enriches LinkedIn profiles autonomously, stores everything in Notion, and identifies overlapping employment periods.

## How It Works

1. **Add Contacts** (your network) and **Leads** (targets) via Streamlit UI
2. **Click "Enrich"** on any contact or lead to scrape their LinkedIn experience autonomously
3. The LLM parses work history and stores it in Notion
4. **Matching Engine** automatically finds shared companies with overlapping employment dates
5. **View matches** to discover warm introduction paths

## Architecture

```
Streamlit UI (Contacts, Leads, Matches, Settings)
    |
    ├─> Chrome (via AppleScript) -> LinkedIn experience page
    ├─> LLM (Gemini/Anthropic/Ollama) -> parse work history
    └─> Notion API -> store data + run matching engine
                |
            Matching Rules (Protocol-based, extensible)
```

- **Enrichment**: LinkedIn scraping via AppleScript (uses existing Chrome session) + LLM-based work history extraction
- **LLM Providers**: Gemini (default), Anthropic Claude, or Ollama (local, M1/M3 compatible with CPU mode)
- **Storage**: Notion databases (Contacts, Leads, Work History, Matches)
- **Matching Rules**: Protocol-based, extensible. V1 rule: shared workplace with overlapping employment dates

## Setup

### 1. Prerequisites

- **macOS** (uses AppleScript to control Chrome)
- Python 3.9+
- Chrome browser (must be running with LinkedIn logged in)
- A Notion workspace with an integration (API token)
- At least one LLM API key:
  - **Gemini** (free tier available via Google Cloud Console)
  - **Anthropic Claude** (paid, $0.80/M input tokens)
  - **Ollama** (free, local — requires 16GB+ RAM, works on M1/M3 Mac)

### 2. Create Notion Databases

The tool auto-creates database schemas on first run. Create four empty databases (no need to pre-configure properties):

- **Contacts** — your core network
- **Leads** — target leads to match against
- **Work History** — enriched employment data (auto-schema)
- **Matches** — discovered warm introduction paths

Copy each database ID from its URL (the 32-character alphanumeric string after `/database/`).

### 3. Install

```bash
git clone https://github.com/[your-username]/Connections.git
cd Connections
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 4. Configure

Copy environment template and add your API keys:

```bash
cp .env.example .env
```

Edit `.env` with:
- `NOTION_API_KEY`: From Notion integrations
- `NOTION_CONTACTS_DB_ID`, `NOTION_LEADS_DB_ID`, `NOTION_WORK_HISTORY_DB_ID`, `NOTION_MATCHES_DB_ID`
- **At least one LLM provider**:
  - `GOOGLE_API_KEY` + `GEMINI_MODEL` (e.g., `gemini-2.5-flash`)
  - `ANTHROPIC_API_KEY` + `ANTHROPIC_MODEL` (e.g., `claude-3-5-sonnet-20241022`)
  - `OLLAMA_BASE_URL` (e.g., `http://localhost:11434`) + `OLLAMA_MODEL` (e.g., `llama2`)
- `LLM_PROVIDER` to pick primary provider (e.g., `gemini`)

### 5. Run

```bash
streamlit run app.py
```

Browser opens to http://localhost:8501 with Contacts, Leads, Matches, and Settings pages.

### 6. Enrich a Contact

1. On the **Contacts** page, add a contact with their LinkedIn profile URL
2. Click the **Enrich** button next to their name
3. The tool navigates to their LinkedIn profile via Chrome, extracts work history, and stores it automatically
4. Matching runs immediately — check **Matches** page to see warm paths

### 7. Test

```bash
pytest tests/ -v
```

All 20 tests pass (matching engine, index building, deduplication).

## Adding New Matching Rules

The matching engine is protocol-based and extensible:

1. Create a file in `src/engine/rules/` (e.g., `shared_investor.py`)
2. Implement the `MatchRule` protocol:
   ```python
   class SharedInvestorRule:
       name = "SharedInvestor"
       description = "Finds leads whose company shares an investor with a contact's company"

       def find_matches(self, contact_histories, lead_histories, index):
           # Your matching logic here
           return [Match(...), ...]
   ```
3. Register it in `src/engine/rules/registry.py`

No changes needed to the matching engine or UI.

## Project Structure

```
src/
  config.py              # Pydantic Settings (.env loader)
  app.py                 # Streamlit entry point
  models/                # Pydantic data models (Contact, Lead, Match, WorkHistoryEntry)
  data/
    linkedin_scraper.py  # AppleScript-based LinkedIn automation
    llm_parser.py        # Multi-provider LLM for work history extraction (Gemini/Anthropic/Ollama)
    linkedin.py          # LinkedIn date parsing + seniority inference
    notion_store.py      # Notion CRUD for all 4 databases + auto-schema
  engine/
    index.py             # CompanyTimeIndex (efficient matching via inverted index)
    matcher.py           # Orchestrates index building + rule execution + dedup
    rules/
      base.py            # MatchRule Protocol
      shared_workplace.py # Rule: overlapping employment at same company
      registry.py        # Rule registration
  pages/                 # Streamlit multi-page UI (Contacts, Leads, Matches, Settings)
tests/                   # Unit tests (20 passing tests for engine)
scripts/
  enrich.py              # CLI: --list, --enrich, --store, --match-all
```

## Key Design Decisions

- **No Agents**: Streamlit UI orchestrates the pipeline directly with immediate execution
- **No External Data APIs**: LinkedIn is the source; no Dealigence dependency
- **Multi-Provider LLMs**: Choose provider at runtime via settings; swap between Gemini/Anthropic/Ollama
- **AppleScript Automation**: Uses existing Chrome session (no separate login needed)
- **Autonomous Enrichment**: Click "Enrich" button, everything runs in the background
