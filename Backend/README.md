# 🧭 Wayfinder AI — Django Backend & Travel Operating System

> Centralized travel intelligence platform combining Python Django, Amadeus for Developers, Booking.com Affiliate Monetization, and Multi-Agent AI Orchestration (Gemini & Model Context Protocol).

---

## 🚀 Quickstart

### 1. Prerequisites
- Python 3.13+
- `uv` (recommended) or standard `python3 -m venv`

### 2. Setup Virtual Environment & Dependencies
```bash
cd Backend
uv venv .venv --python 3.13
source .venv/bin/activate
uv pip install -r requirements.txt
```

### 3. Initialize Centralized Database
```bash
python manage.py migrate
python manage.py seed_airports      # Seeds 23 global airport hubs (JFK, NRT, LHR, CDG, etc.)
python manage.py create_dev_admin   # Creates admin / admin123 for GUI at /admin
```

### 4. Run Development Server
```bash
python manage.py runserver 8000
```
Open **`http://localhost:8000/`** to view the live Interactive Workspace, or **`http://localhost:8000/admin/`** for the Django Admin GUI.

### 5. Run Pytest Test Suite
```bash
pytest -v
```

---

## 🏗️ Architecture & Apps

| App | Purpose | Key Models & Services |
| :--- | :--- | :--- |
| **`apps.catalog`** | Centralized travel database | `Airport`, `MasterHotel`, `FlightOffer`, `TravelIngestionService` |
| **`apps.providers`** | Provider adapters & monetization | `AmadeusProviderService`, `MockTravelProvider`, `BookingAffiliateService` |
| **`apps.trips`** | Trip planning & itineraries | `Trip`, `ItineraryDay`, `TripShortlist`, REST ViewSets |
| **`apps.agents`** | Multi-agent swarm & MCP tools | `TravelCoordinatorAgent`, Specialist Agents, MCP Tool Registry |
| **`apps.bookings`** | Auditable state machine & safety | `BookingRecord`, `BookingStateMachine` (`DRAFT` → `CONFIRMED`) |

---

## 🔌 Provider Mode & Affiliate Configuration (`.env`)

```env
# Switch between offline mock and live Amadeus API
PROVIDER_MODE=mock # or 'amadeus'
AMADEUS_CLIENT_ID=your_amadeus_api_key
AMADEUS_CLIENT_SECRET=your_amadeus_secret
AMADEUS_ENVIRONMENT=test

# Booking.com Affiliate ID
BOOKING_AFFILIATE_ID=your_affiliate_id

# Google Gemini API
GEMINI_API_KEY=your_gemini_key
GEMINI_MODEL=gemini-2.5-flash
```

---

## 🛡️ The Booking Safety Guarantee
No LLM or agent can finalize a purchase. Transitions through the state machine:
$$\text{DRAFT} \longrightarrow \text{QUOTE\_VALIDATED} \longrightarrow \text{AWAITING\_APPROVAL} \longrightarrow \text{SUBMITTED} \longrightarrow \text{CONFIRMED}$$
require live price re-verification and explicit human approval token authentication.

