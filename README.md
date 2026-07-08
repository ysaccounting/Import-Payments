# CSV Import to TicketVault

Remittance file converter — transforms network payout files into TicketVault-ready CSVs.

## Supported networks
Gametime, GoTickets, Mercury, SeatGeek, StubHub, StubHub ($0), Ticket Evolution, TicketNetwork, TicketsNow, TicketsNow (CAD), TickPick, Vivid Seats, Vivid Seats (CAD)

## Output columns
`order#`, `amount`, `remittancedate`, `chargebackreason`

## Project structure
```
app.py            ← Flask backend
index.html        ← Frontend UI
parsers.py        ← All network file parsers
requirements.txt  ← Dependencies
railway.json      ← Railway deployment config
```

## Run locally
```bash
pip install -r requirements.txt
python app.py     # http://localhost:5000
```

## Deploy to Railway
1. Push repo to GitHub
2. Railway → New Project → Deploy from GitHub repo
3. Railway auto-detects Python via Nixpacks and uses railway.json for the start command
