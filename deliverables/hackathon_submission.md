# GridKey: AI-Powered Battery Storage Optimizer

## Problem Statement

The energy transition is creating unprecedented volatility in European electricity markets. Battery Energy Storage Systems (BESS) operators face a complex optimization challenge: they must simultaneously navigate four distinct revenue streams—Day-Ahead markets, Frequency Containment Reserve (FCR), and automatic Frequency Restoration Reserve (aFRR) capacity and energy markets—while accounting for renewable generation variability and battery degradation costs.

Current solutions require specialized energy trading expertise and manual analysis of multiple data sources: weather forecasts, market prices, and grid conditions. Small-to-medium BESS operators lack the resources to develop sophisticated optimization software, leaving significant revenue on the table. Industry estimates suggest suboptimal scheduling can reduce profits by 20-40%.

**The core challenge**: How can we democratize access to advanced battery optimization, making it as simple as asking a question in natural language?

## Solution: GridKey with WatsonX Agentic AI

GridKey is an intelligent battery storage optimization platform that combines Mixed-Integer Linear Programming (MILP) optimization with IBM WatsonX's agentic AI capabilities. Our solution transforms complex energy trading decisions into a conversational experience.

### How It Works

A user simply asks: *"What's the weather in Munich tomorrow? Optimize my battery schedule for maximum profit."*

Behind the scenes, GridKey's WatsonX Agent orchestrates a sophisticated workflow:

1. **Weather Intelligence**: Fetches real-time forecasts from OpenWeatherMap API, calculates expected solar PV and wind generation using physics-based models (irradiance → power conversion with temperature derating)

2. **Market Analysis**: Retrieves electricity prices across four markets (ENTSO-E for Day-Ahead, regelleistung.net for FCR/aFRR), identifying optimal arbitrage windows and reserve participation opportunities

3. **MILP Optimization**: Runs our proven optimization engine that maximizes total revenue while respecting:
   - Battery state-of-charge constraints (20-90%)
   - C-rate power limits
   - Market-specific participation rules
   - Degradation costs (cycle-based aging model)

4. **Natural Language Explanation**: Converts the mathematical solution into actionable recommendations:
   > "Tomorrow Munich will be sunny with 18.5 kWh expected PV generation. Charge at 2-5 AM (€32/MWh), participate in FCR at 8-10 AM, let solar charge your battery at noon, then discharge during the evening peak (€89/MWh). Expected profit: €127."

### Climate Impact

GridKey directly accelerates the energy transition by:
- **Maximizing renewable self-consumption**: Our optimizer prioritizes using solar/wind generation to charge batteries, reducing curtailment
- **Enabling grid flexibility**: BESS operators providing FCR/aFRR services help stabilize grids with high renewable penetration
- **Democratizing clean energy economics**: Making advanced optimization accessible encourages more BESS deployments

### Technical Differentiation

Unlike black-box AI solutions, GridKey combines:
- **Explainable MILP optimization** with mathematical guarantees
- **Real-time data integration** (weather + 4 market price feeds)
- **WatsonX Orchestrate** for tool orchestration and natural language interaction
- **Transparent recommendations** users can understand and trust

GridKey transforms battery storage from a complex engineering problem into a simple conversation—accelerating the clean energy transition one optimized schedule at a time.

---

*Built with IBM WatsonX Orchestrate, FastAPI, Python, and HiGHS solver.*
