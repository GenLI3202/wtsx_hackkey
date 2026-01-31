# Repository Structure Plan for IBM Hackathon

This document outlines the recommended folder structure for your project. This structure is designed to meet the IBM Hackathon deliverables while maintaining a clean separation of concerns, especially for the external "Optimizer Service".

## Deliverables Checklist & Locations
| Deliverable | Location in Repo |
| :--- | :--- |
| **1. Video demonstration** | `deliverables/demonstration_video.mp4` (or link in README) |
| **2. Problem & Solution Statements** | `deliverables/problem_solution.md` |
| **3. Agentic AI & WatsonX Usage** | `deliverables/ai_orchestrate_usage.md` |
| **4. Working Code** | `src/` |

## Proposed Directory Tree

```text
/
├── .gitignore                # [CRITICAL] Prevents committing secrets/env files
├── .env.template             # Template for env vars (API Keys, etc.) - DO NOT fill real keys here
├── README.md                 # Project entry point & Setup guide
├── requirements.txt          # Python dependencies
├── architecture.md           # The architecture reference doc
│
├── deliverables/             # [IBM Req] Folders for contest deliverables
│   ├── demonstration_video.md   # Link to video or placeholder for the file
│   ├── problem_solution.md      # Deliverable #2
│   └── ai_orchestrate_usage.md  # Deliverable #3
│
├── docs/                     # Additional documentation
│   └── api_docs/             # API specifications
│
├── src/                      # Source code
│   ├── __init__.py
│   ├── backend/
│   │   ├── __init__.py
│   │   ├── main.py           # FastAPI/Gateway entry point
│   │   ├── config.py         # Configuration loader
│   │   │
│   │   ├── agent/            # Module E: WatsonX Agent Layer
│   │   │   ├── __init__.py
│   │   │   ├── client.py     # WatsonX SDK wrapper
│   │   │   └── tools.py      # Tools definition for the agent
│   │   │
│   │   └── services/         # Core Services
│   │       ├── __init__.py
│   │       ├── weather.py    # Module A: Weather Service (External API + Logic)
│   │       ├── price.py      # Module B: Price Service (External API)
│   │       ├── battery.py    # Module C: Battery Service (Mock/Local)
│   │       └── optimizer.py  # Module D: CLIENT/Interface to external Optimizer API
│   │
│   └── frontend/             # Module F: User Interface
│       ├── __init__.py
│       ├── app.py            # Streamlit entry point
│       └── components/       # UI Components
│
├── tests/                    # Unit and integration tests
│   ├── __init__.py
│   ├── test_weather.py
│   └── test_agent.py
│
└── scripts/                  # Helper scripts
    └── setup_env.bat         # Script to help init environment
```

## Module Mapping

- **Module A (Weather)** -> `src/backend/services/weather.py`
- **Module B (Price)** -> `src/backend/services/price.py`
- **Module C (Battery)** -> `src/backend/services/battery.py`
- **Module D (Optimizer)** -> `src/backend/services/optimizer.py`
  - *Note: This file will contain the HTTP Client code to call your other repo's API.*
- **Module E (WatsonX)** -> `src/backend/agent/`
- **Module F (Gateway/Frontend)** -> `src/backend/main.py` (API) & `src/frontend/` (UI)

## Important Notes for Initialization

1.  **Secret Management**: The `.gitignore` MUST include `.env`. Use `.env.template` to show required variables (e.g., `IBM_CLOUD_API_KEY`, `OPENWEATHER_API_KEY`) without values.
2.  **Optimizer Service**: Since the core logic is in another repo, `src/backend/services/optimizer.py` should define a class/function that sends data to your external API endpoint.
3.  **Deliverables**: The `deliverables/` folder is explicitly created to ensure you don't miss any submission requirements.
