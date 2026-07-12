# 🌊 Fisherman OS — Small-Scale Fisherman Intelligence OS

> **The Intelligence Layer Between the Ocean and the Fisherman — Delivered on WhatsApp.**

[![Idea Validation Score](https://img.shields.io/badge/Validation%20Score-27%2F30%20Strong%20Go-00d4aa?style=for-the-badge)](./idea_validation_report.md)
[![Target Market](https://img.shields.io/badge/TAM-%2422.95B-0077b6?style=for-the-badge)](./idea_validation_report.md)
[![Delivery Mechanism](https://img.shields.io/badge/Delivery-WhatsApp%20Native-25D366?style=for-the-badge)](./index.html)

---

## ⚡ Executive Summary

India has approximately **4 million traditional/artisanal fishermen** who go out daily in small boats. Today, their decision-making relies on WhatsApp group rumors, personal intuition, and occasionally checking web weather maps they mostly cannot read. 

The result:
- **Dangerous weather decisions:** 775 fishermen killed and 113 missing in Kerala alone (2011–2024).
- **Wasted fuel:** Diesel accounts for 60–70% of trip costs. Fishermen burn hours scouting blindly for fish.
- **Price exploitation:** Zero price transparency across landing centers leads to 40% income loss to middlemen.

**Fisherman OS** solves this by delivering hyperlocal **1km × 1km sea state forecasts (via ISRO/INCOIS)**, **AI-driven fish migration zone recommendations**, **real-time market prices**, and an **SOS distress beacon** directly through a **native WhatsApp chatbot in vernacular languages (Konkani, Malayalam, Tamil)**. No app downloads required.

---

## 🚀 Key Deliverables in this Repository

| Deliverable | Description | File Link |
|:---|:---|:---|
| 🤖 **Phase 1 Backend (Goa MVP)** | Working WhatsApp-bot backend: 3:30 AM forecast push, market prices, SOS flow, onboarding, Konkani/Hindi/Marathi localization, 78-test suite | [`backend/`](./backend/) |
| 🌐 **Interactive Pitch Deck** | Stunning 11-slide responsive landing page with interactive WhatsApp chat simulation & financial models | [`index.html`](./index.html) |
| 📊 **Validation Report** | Complete 27/30 scored business validation, pressure tests, competitor analysis, & data network effect moat | [`idea_validation_report.md`](./idea_validation_report.md) |
| 🗺️ **Execution Plan & MVP Roadmap** | Detailed 30-month 4-phase blueprint, system architecture, WhatsApp bot specification, & budget | [`execution_plan.md`](./execution_plan.md) |

---

## 🚧 Phase 1 (Goa MVP) — Implemented

The [`backend/`](./backend/) directory contains the working Phase 1 system from the
[execution plan](./execution_plan.md): a FastAPI + PostgreSQL backend behind a
Gupshup WhatsApp webhook, with:

- **Feature 1 — Morning Forecast:** INCOIS Ocean State Forecast pipeline (with
  OpenWeatherMap and synthetic fallbacks), 🟢🟡🔴 sea-safety classification, and a
  3:30 AM IST auto-push per village.
- **Feature 2 — Market Prices:** field-agent price entry (admin API + WhatsApp
  `PRICE` command), FMPIS ingestion hook, 5 AM digest, and the "💡 Margao paying
  29% more" best-market tip.
- **Feature 3 — SOS:** always-on distress flow with Coast Guard 1554, emergency
  contact alerts, live location relay every 5 minutes, and CANCEL stand-down.
- **Onboarding:** send "Hi" → language → name → village → boat type → first
  forecast immediately. 41 South Goa villages and 5 landing centers seeded.
- **Localization:** English, Konkani (Romi), Hindi, Marathi.
- **Ops:** KPI metrics endpoint (registered vs 500 target, DAU vs 60% target,
  SOS counts), broadcast tool, Docker/Compose, CI.

See [`backend/README.md`](./backend/README.md) for setup and the deploy checklist.

---

## 📱 How It Works (The WhatsApp Experience)

Instead of forcing fishermen to download yet another app (where 97.8% drop off), Fisherman OS meets them where they already spend hours daily: **WhatsApp**.

```
🌊 Fisherman OS — Betul Landing
📅 8 July 2026 | 3:30 AM

☀️ Today's Sea: 🟢 SAFE TO GO

🌬️ Wind: 12 km/h SW
🌊 Waves: 0.8m (calm)
🌧️ Rain: 20% chance after 2PM
🌡️ Sea temp: 28.5°C

⚠️ Return before 2PM — afternoon squall risk
Next 6 hours: 🟢🟢🟢🟡🟡🟡

---
🐟 Today's Market Prices (Margao paying highest! ↑29%)
📍 Betul: Mackerel ₹85 | Pomfret ₹320
📍 Margao: Mackerel ₹110 | Pomfret ₹380
```

---

## 💡 The Moat: Crowd-Sourced Catch Data Flywheel

```
Fisherman Logs Catch ("CATCH mackerel 50kg")
       │
       ▼
AI Improves Predictions (Correlating SST + Chlorophyll with actual catch)
       │
       ▼
Better Fish Zone Advice ("Head 12km SW of Betul today")
       │
       ▼
More Fishermen Join & Log Catch (Network Effect + Cooperative Lock-In)
```

---

## 💻 Viewing the Pitch Deck Locally

1. Clone or download this repository:
   ```bash
   git clone https://github.com/adit-tambe/Fisherman-OS.git
   ```
2. Open `index.html` in any web browser (`Chrome`, `Firefox`, `Safari`, `Edge`).
3. Enjoy the dark ocean aesthetic, interactive WhatsApp chat simulation, and animated financial models!

---

## 📈 Financial & Impact Snapshot

- **TAM:** $22.95 Billion (Indian Marine Fisheries Market)
- **SAM:** $5.4 Billion (Annual Operations & Fuel Spend of Smartphone-Enabled Artisanal Fishermen)
- **SOM (Year 3):** ₹20 Crore ARR across 100,000 active fishermen
- **Immediate Impact:** **60% reduction in scouting fuel costs** + **₹17,820 additional income potential per trip** (verified by INCOIS/Stanford studies).

---

## 📄 License & Contact

Built with ❤️ for India's Coastal Communities and Blue Economy.
Contact: [`hello@fishermanos.in`](mailto:hello@fishermanos.in)
