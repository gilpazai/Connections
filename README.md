# VC Connections

A modular VC networking tool that maps warm introduction paths by comparing LinkedIn work histories of your core network against monthly target leads.

## How It Works

1. **Add Contacts** (your core network) and **Leads** (monthly targets) via the web UI
2. **Run the Pipeline** to enrich people with work history data from Dealigence
3. The **Matching Engine** finds overlapping employment periods at the same company
4. **Introduction Drafts** are auto-generated for each discovered connection

## Architecture

```
Streamlit UI -> Agno Agents -> Dealigence (data) + Notion (storage)
                    |
              Rules Engine (extensible matching)
```

- **Data Source**: Dealigence API for work history enrichment
- **Storage**: Notion databases (Contacts, Leads, Work History, Matches)
- **Agents**: Agno framework with Claude (Ingestion, Matching, Reporting)
- **Rules Engine**: Protocol-based, extensible. V1 rule: shared workplace with overlapping dates

## Setup

### 1. Prerequisites

- Python 3.9+
- A Notion workspace with an integration (API token)
- An Anthropic API key
- A Dealigence API key (optional, for auto-enrichment)

### 2. Create Notion Databases

Create four databases in your Notion workspace. Each must have the exact property names below.

**Contacts DB**: Name (title), LinkedIn URL (url), Company (Current) (rich_text), Title (Current) (rich_text), Relationship Strength (select: Close/Medium/Loose), Tags (multi_select), Dealigence Person ID (rich_text), Last Enriched (date), Status (select: Active/Inactive), Notes (rich_text)

**Leads DB**: Name (title), LinkedIn URL (url), Company (Current) (rich_text), Title (Current) (rich_text), Priority (select: High/Medium/Low), Batch (rich_text), Dealigence Person ID (rich_text), Last Enriched (date), Status (select: New/Enriched/Matched/Contacted/Converted), Notes (rich_text)

**Work History DB**: Person Name (title), Person Type (select: Contact/Lead), Employer Name (rich_text), Employer Dealigence ID (rich_text), Role Title (rich_text), Seniority (select: Founder/VP-C-Level/Managerial/Hands-on), Start Date (date), End Date (date), Tenure Years (number), Source Person ID (rich_text)

**Matches DB**: Title (title), Contact Name (rich_text), Lead Name (rich_text), Shared Company (rich_text), Overlap Start (date), Overlap End (date), Overlap Months (number), Contact Role (rich_text), Lead Role (rich_text), Match Rule (select: SharedWorkplace), Confidence (select: High/Medium/Low), Status (select: New/Reviewed/Acting/Done/Dismissed), Intro Draft (rich_text)

### 3. Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
pip install fastapi  # required by agno.workflow
```

### 4. Configure

```bash
cp .env.example .env
```

Edit `.env` with your API keys and Notion database IDs (found in each database's URL).

### 5. Run

```bash
streamlit run app.py
```

### 6. Test

```bash
pytest tests/ -v
```

## Adding New Matching Rules

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
3. Register it in `src/engine/rules/registry.py`:
   ```python
   def create_default_registry():
       registry = RuleRegistry()
       registry.register(SharedWorkplaceRule())
       registry.register(SharedInvestorRule())  # add here
       return registry
   ```

No changes needed to the matching engine, agents, or UI.

## Project Structure

```
src/
  config.py          # Pydantic Settings (.env loader)
  models/            # Pydantic data models (Contact, Lead, Match, WorkHistoryEntry)
  data/
    dealigence.py    # Dealigence API wrapper + work history parsing
    notion_store.py  # Notion CRUD for all 4 databases
  engine/
    index.py         # CompanyTimeIndex (inverted index for efficient matching)
    matcher.py       # Orchestrates index building + rule execution + dedup
    rules/
      base.py        # MatchRule Protocol
      shared_workplace.py  # V1 rule: overlapping employment
      registry.py    # Rule registration
  agents/
    ingestion_agent.py   # Enriches people via Dealigence
    matching_agent.py    # Runs rules engine
    reporting_agent.py   # Generates intro drafts
    tools/               # Agno Toolkits wrapping data/engine layers
  workflows/
    pipeline.py      # Sequential pipeline: ingest -> match -> report
  pages/             # Streamlit UI pages
tests/               # Unit tests for engine components
```
