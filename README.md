# CSV Import to TicketVault

Remittance file converter — transforms network payout files into TicketVault-ready CSVs.

## Supported networks
Gametime, GoTickets, Mercury, SeatGeek, StubHub, Ticket Evolution, TicketNetwork, TicketsNow, TicketsNow (CAD), TickPick, Vivid Seats, Vivid Seats (CAD)

## Output columns
`order#`, `amount`, `remittancedate`, `chargebackreason`

## Project structure
```
app.py            ← Main app
parsers.py        ← All network file parsers
requirements.txt  ← Dependencies
```

## Setup

### 1. Clone & install
```bash
git clone https://github.com/YOUR_USERNAME/csv-import-to-tv.git
cd csv-import-to-tv
pip install -r requirements.txt
```

### 2. Run locally
```bash
python -m streamlit run app.py
```

### 3. Deploy to Railway
1. Push repo to GitHub
2. Create new project on Railway
3. Connect your GitHub repo
4. Set start command to: `python -m streamlit run app.py --server.port $PORT --server.address 0.0.0.0`
