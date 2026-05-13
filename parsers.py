import pandas as pd
import io


def _read(file) -> bytes:
    """Read a file-like object, seeking to start first (handles Streamlit's UploadedFile)."""
    if hasattr(file, 'seek'):
        file.seek(0)
    return file.read()


def _clean_amount(val):
    """Strip $, commas, whitespace and return float."""
    if pd.isna(val):
        return 0.0
    return float(str(val).replace("$", "").replace(",", "").strip() or 0)


# ── Vivid Seats ───────────────────────────────────────────────────────────────
def parse_vivid(file) -> pd.DataFrame:
    content = _read(file).decode("utf-8", errors="replace")
    lines = content.splitlines()
    header_idx = None
    for i, line in enumerate(lines):
        if line.strip().lower().startswith("po #") or line.strip().lower().startswith("po#"):
            header_idx = i
            break
    if header_idx is None:
        return None
    csv_str = "\n".join(lines[header_idx:])
    df = pd.read_csv(io.StringIO(csv_str))
    df.columns = [c.strip() for c in df.columns]
    order_col = next((c for c in df.columns if c.strip().lower().replace(" ", "") == "order#"), None)
    amt_col   = next((c for c in df.columns if c.strip().lower() == "amount"), None)
    if not order_col or not amt_col:
        return None
    out = pd.DataFrame()
    out["order#"]          = df[order_col].astype(str).str.strip()
    out["amount"]          = df[amt_col].apply(_clean_amount)
    out["chargebackreason"] = ""
    return out.dropna(subset=["order#"]).reset_index(drop=True)


# ── Gametime ──────────────────────────────────────────────────────────────────
def parse_gametime(file) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(_read(file)))
    df.columns = [c.strip() for c in df.columns]
    out = pd.DataFrame()
    out["order#"]          = df["#"].astype(str).str.strip()
    out["amount"]          = df["Payout"].apply(_clean_amount)
    out["chargebackreason"] = df["Reason"].fillna("").astype(str).str.strip() if "Reason" in df.columns else ""
    return out.dropna(subset=["order#"]).reset_index(drop=True)


# ── GoTickets ─────────────────────────────────────────────────────────────────
def parse_gotickets(file) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(_read(file)))
    df.columns = [c.strip() for c in df.columns]
    out = pd.DataFrame()
    out["order#"]          = df["Order ID"].astype(str).str.strip()
    out["amount"]          = df["Amount"].apply(_clean_amount)
    out["chargebackreason"] = ""
    return out.dropna(subset=["order#"]).reset_index(drop=True)


# ── SeatGeek ──────────────────────────────────────────────────────────────────
def parse_seatgeek(file) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(_read(file)))
    df.columns = [c.strip().strip('"') for c in df.columns]
    out = pd.DataFrame()
    out["order#"]          = df["Order ID"].astype(str).str.strip().str.strip('"')
    out["amount"]          = df["Amount"].apply(_clean_amount)
    out["chargebackreason"] = df["Reason"].fillna("").astype(str).str.strip().str.strip('"') if "Reason" in df.columns else ""
    return out.dropna(subset=["order#"]).reset_index(drop=True)


# ── TicketsNow ────────────────────────────────────────────────────────────────
def parse_ticketsnow(file) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(_read(file)))
    df.columns = [c.strip() for c in df.columns]
    out = pd.DataFrame()
    out["order#"]          = df["Web Order #"].astype(str).str.strip()
    out["amount"]          = df["Amount"].apply(_clean_amount)
    out["chargebackreason"] = ""
    return out.dropna(subset=["order#"]).reset_index(drop=True)


# ── TickPick (xlsx) ───────────────────────────────────────────────────────────
def parse_tickpick(file) -> pd.DataFrame:
    df = pd.read_excel(io.BytesIO(_read(file)))
    df.columns = [c.strip() for c in df.columns]
    out = pd.DataFrame()
    out["order#"]          = df["Order Number"].astype(str).str.strip()
    out["amount"]          = df["Amount"].apply(_clean_amount)
    out["chargebackreason"] = ""
    return out.dropna(subset=["order#"]).reset_index(drop=True)


# ── StubHub / Viagogo ─────────────────────────────────────────────────────────
def parse_stubhub(file) -> pd.DataFrame:
    raw = _read(file)
    content = None
    for enc in ("utf-16", "utf-8", "latin-1", "cp1252"):
        try:
            content = raw.decode(enc)
            break
        except (UnicodeDecodeError, UnicodeError):
            continue

    lines = content.splitlines()
    if not lines:
        return None

    header_cols = [c.strip().lower() for c in lines[0].split(",")]
    rows_out = []

    # ── Format A: PaymentID, Date, Proceeds, Charges, Credit, Total ──────────
    if "paymentid" in header_cols:
        order_idx   = header_cols.index("paymentid")
        proc_idx    = header_cols.index("proceeds")  if "proceeds" in header_cols else -1
        charg_idx   = header_cols.index("charges")   if "charges"  in header_cols else -1
        credit_idx  = header_cols.index("credit")    if "credit"   in header_cols else -1
        for line in lines[1:]:
            if not line.strip():
                continue
            parts = line.split(",")
            order    = parts[order_idx].strip().strip('"') if order_idx < len(parts) else ""
            if not order:
                continue
            proceeds = _clean_amount(parts[proc_idx])   if proc_idx   != -1 and proc_idx   < len(parts) else 0
            charges  = _clean_amount(parts[charg_idx])  if charg_idx  != -1 and charg_idx  < len(parts) else 0
            credit   = _clean_amount(parts[credit_idx]) if credit_idx != -1 and credit_idx < len(parts) else 0
            amount   = proceeds + charges + credit
            rows_out.append({"order#": order, "amount": round(amount, 2), "chargebackreason": ""})

    # ── Format B: EventName, Venue, EventDate, TransactionID, Proceeds, Charges, Credit, Description ──
    elif "transactionid" in header_cols:
        for line in lines[1:]:
            if not line.strip():
                continue
            parts = line.split(",")
            if len(parts) < 8:
                continue
            description = parts[-1].strip().strip('"')
            credit      = _clean_amount(parts[-2])
            charges     = _clean_amount(parts[-3])
            proceeds    = _clean_amount(parts[-4])
            transaction = parts[-5].strip().strip('"')
            if not transaction:
                continue
            amount     = proceeds + charges + credit
            chargeback = "" if description.lower() == "proceeds" else description
            rows_out.append({"order#": transaction, "amount": round(amount, 2), "chargebackreason": chargeback})

    if not rows_out:
        return None
    return pd.DataFrame(rows_out).reset_index(drop=True)


# ── Ticket Evolution ──────────────────────────────────────────────────────────
def parse_ticket_evolution(file, date_start=None, date_end=None) -> pd.DataFrame:
    raw = _read(file)
    content = raw.decode("utf-8", errors="replace")
    lines = content.splitlines()

    # Find header row
    header_idx = None
    for i, line in enumerate(lines):
        if "order - po #" in line.lower():
            header_idx = i
            break
    if header_idx is None:
        return None

    csv_str = "\n".join(lines[header_idx:])
    df = pd.read_csv(io.StringIO(csv_str))
    df.columns = [c.strip().strip('"') for c in df.columns]

    # Skip withdrawals
    df = df[df["Type"].str.strip().str.lower() != "withdrawal"].copy()

    # Filter by date range if provided
    # Date format in file: "04-30-2026 04:02 pm"
    if date_start or date_end:
        date_col = next((c for c in df.columns if c.strip().lower() == "date created"), None)
        if date_col:
            df["_date"] = pd.to_datetime(
                df[date_col].astype(str).str.strip().str.strip('"'),
                format="%m-%d-%Y %I:%M %p",
                errors="coerce"
            ).dt.date
            if date_start:
                df = df[df["_date"] >= date_start]
            if date_end:
                df = df[df["_date"] <= date_end]

    po_col = next((c for c in df.columns if "po #" in c.lower()), None)
    if not po_col:
        return None

    df["_credit"] = df["Credit"].apply(_clean_amount)
    df["_debit"]  = df["Debit"].apply(_clean_amount)
    df["_net"]    = df["_credit"] - df["_debit"]
    df["_po"]     = df[po_col].astype(str).str.strip()

    grouped = df.groupby("_po")["_net"].sum().reset_index()
    grouped["_net"] = grouped["_net"].round(2)

    out = pd.DataFrame()
    out["order#"]           = grouped["_po"]
    out["amount"]           = grouped["_net"]
    out["chargebackreason"] = ""
    return out.reset_index(drop=True)


# ── TicketNetwork (csv — two files: Details + Adjustments) ──────────────────
def parse_ticketnetwork(file) -> pd.DataFrame:
    raw = _read(file)
    content = raw.decode("utf-8", errors="replace")
    lines = content.splitlines()
    if not lines:
        return None
    headers = [c.strip().upper() for c in lines[0].split(",")]
    rows_out = []

    # ── Details file (has TOTAL column) ──────────────────────────────────────
    if "TOTAL" in headers:
        order_col = headers.index("ORDER ID")
        total_col = headers.index("TOTAL")
        for line in lines[1:]:
            if not line.strip():
                continue
            cols  = line.split(",")
            order = (cols[order_col] if order_col < len(cols) else "").strip()
            amt   = _clean_amount(cols[total_col] if total_col < len(cols) else "")
            if not order:
                continue
            rows_out.append({"order#": order, "amount": amt, "chargebackreason": ""})

    # ── Adjustments file (has ADJUSTMENT AMOUNT column) ───────────────────────
    elif "ADJUSTMENT AMOUNT" in headers:
        order_col  = headers.index("ORDER ID")
        amt_col    = headers.index("ADJUSTMENT AMOUNT")
        reason_col = headers.index("ADJUSTMENT CATEGORY") if "ADJUSTMENT CATEGORY" in headers else -1
        for line in lines[1:]:
            if not line.strip():
                continue
            # Use csv reader to handle quoted fields
            import csv, io as _io
            cols   = next(csv.reader(_io.StringIO(line)))
            order  = (cols[order_col] if order_col < len(cols) else "").strip()
            amt    = -abs(_clean_amount(cols[amt_col] if amt_col < len(cols) else ""))
            reason = (cols[reason_col] if reason_col != -1 and reason_col < len(cols) else "").strip()
            if not order:
                continue
            rows_out.append({"order#": order, "amount": round(amt, 2), "chargebackreason": reason})

    if not rows_out:
        return None
    return pd.DataFrame(rows_out).reset_index(drop=True)

# ── Mercury (csv — Details + Adjustments files) ──────────────────────────────
def parse_mercury(file) -> pd.DataFrame:
    raw = _read(file)
    content = raw.decode("utf-8", errors="replace")
    lines = content.splitlines()
    if not lines:
        return None
    headers = [c.strip().upper() for c in lines[0].split(",")]
    rows_out = []

    # ── Details file: MERCURY_TRANSACTION_ID, WHOLESALE_AMT, FEE_AMT ─────────
    if "MERCURY_TRANSACTION_ID" in headers:
        order_col = headers.index("MERCURY_TRANSACTION_ID")
        whl_col   = headers.index("WHOLESALE_AMT")
        fee_col   = headers.index("FEE_AMT")
        for line in lines[1:]:
            if not line.strip():
                continue
            cols  = line.split(",")
            order = (cols[order_col] if order_col < len(cols) else "").strip()
            whl   = _clean_amount(cols[whl_col] if whl_col < len(cols) else "")
            fee   = _clean_amount(cols[fee_col] if fee_col < len(cols) else "")
            if not order:
                continue
            rows_out.append({"order#": order, "amount": round(whl - fee, 2), "chargebackreason": ""})

    # ── Adjustments file: ORDER ID, ADJUSTMENT AMOUNT, ADJUSTMENT CATEGORY ────
    elif "ADJUSTMENT AMOUNT" in headers:
        order_col  = headers.index("ORDER ID")
        amt_col    = headers.index("ADJUSTMENT AMOUNT")
        reason_col = headers.index("ADJUSTMENT CATEGORY") if "ADJUSTMENT CATEGORY" in headers else -1
        for line in lines[1:]:
            if not line.strip():
                continue
            import csv, io as _io
            cols   = next(csv.reader(_io.StringIO(line)))
            order  = (cols[order_col] if order_col < len(cols) else "").strip()
            amt    = _clean_amount(cols[amt_col] if amt_col < len(cols) else "")
            reason = (cols[reason_col] if reason_col != -1 and reason_col < len(cols) else "").strip()
            if not order:
                continue
            rows_out.append({"order#": order, "amount": round(amt, 2), "chargebackreason": reason})

    if not rows_out:
        return None
    return pd.DataFrame(rows_out).reset_index(drop=True)

# ── Router ────────────────────────────────────────────────────────────────────
def parse_file(file, network: str, **kwargs) -> pd.DataFrame:
    parsers = {
        "Vivid Seats":      parse_vivid,
        "Gametime":         parse_gametime,
        "GoTickets":        parse_gotickets,
        "SeatGeek":         parse_seatgeek,
        "TicketsNow":       parse_ticketsnow,
        "TickPick":         parse_tickpick,
        "StubHub":          parse_stubhub,
        "Ticket Evolution": parse_ticket_evolution,
        "TicketNetwork":    parse_ticketnetwork,
        "Mercury":          parse_mercury,
    }
    parser = parsers.get(network)
    if parser is None:
        return None
    return parser(file, **kwargs)
