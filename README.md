# GridKey BESS Optimizer + WatsonX Agent

## Overview

This project is an entry for the IBM Dev Day Hackathon. It upgrades the existing GridKey BESS Optimizer by resolving real-time data integration and adding an Agentic AI layer powered by IBM WatsonX.

## Modules

- **Module A: Weather Service**: Fetches real-time weather and predicts renewable generation.
- **Module B: Price Service**: Fetches real-time electricity prices from ENTSO-E.
- **Module C: Battery Service**: Simulates BESS state and degradation.
- **Module D: Optimizer Service**: Interfaces with the core MILP optimization engine.
- **Module E: WatsonX Agent**: Orchestrates tasks via natural language.
- **Module F: App**: Frontend visualization using Streamlit.

## Get Started

- For the repo structure explanation, refer to [repo_structure_plan.md](repo_structure_plan.md)
- For the architecture explanation, refer to [architecture.md](architecture.md)

## Setup

1. Clone the repository.
2. `cp .env.template .env` and fill in your API keys.
3. `pip install -r requirements.txt`
4. Run the app: `streamlit run src/frontend/app.py`
