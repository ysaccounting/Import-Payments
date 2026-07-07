import io
import os
import time
import uuid
import shutil
import tempfile
from datetime import datetime

import pandas as pd
from flask import Flask, request, jsonify, send_file, send_from_directory, abort
from parsers import parse_file

app = Flask(__name__, static_folder=None)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

STORE_DIR = os.path.join(tempfile.gettempdir(), "tv_store")
os.makedirs(STORE_DIR, exist_ok=True)


def _cleanup_old(max_age_seconds=12 * 3600):
    now = time.time()
    for name in os.listdir(STORE_DIR):
        path = os.path.join(STORE_DIR, name)
        try:
            if os.path.isdir(path) and now - os.path.getmtime(path) > max_age_seconds:
                shutil.rmtree(path, ignore_errors=True)
        except OSError:
            pass


@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/process", methods=["POST"])
def process():
    company    = request.form.get("company", "").strip()
    network    = request.form.get("network", "").strip()
    remit_date = request.form.get("remit_date", "").strip()
    date_start = request.form.get("date_start", "").strip() or None
    date_end   = request.form.get("date_end", "").strip()   or None

    if not company or not network or not remit_date:
        return jsonify({"error": "Company, Network, and Remittance Date are required."}), 400

    files = request.files.getlist("files")
    if not files or all(f.filename == "" for f in files):
        return jsonify({"error": "Please upload at least one remittance file."}), 400

    try:
        rd = datetime.strptime(remit_date, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": f"Invalid remittance date: {remit_date}"}), 400

    ds = datetime.strptime(date_start, "%Y-%m-%d").date() if date_start else None
    de = datetime.strptime(date_end,   "%Y-%m-%d").date() if date_end   else None

    try:
        frames = []
        for f in files:
            if f.filename == "":
                continue
            kwargs = {}
            if network == "Ticket Evolution":
                kwargs["date_start"] = ds
                kwargs["date_end"]   = de
            result = parse_file(f, network, **kwargs)
            if result is not None and not result.empty:
                frames.append(result)
        df = pd.concat(frames, ignore_index=True) if frames else None
    except Exception as e:
        return jsonify({"error": f"Could not parse file: {e}"}), 500

    if df is None or df.empty:
        if network == "Ticket Evolution" and (ds or de):
            return jsonify({"error": "No transactions found in the selected date range. Check that the file contains data for those dates."}), 400
        return jsonify({"error": "Could not parse file — check that the file matches the selected network."}), 400

    date_str = f"{rd.month}/{rd.day}/{rd.year}"
    df["remittancedate"] = date_str
    df = df[["order#", "amount", "remittancedate", "chargebackreason"]]
    df = pd.concat([df[df["amount"] >= 0], df[df["amount"] < 0]], ignore_index=True)

    gross          = float(df[df["amount"] > 0]["amount"].sum())
    net            = float(df["amount"].sum())
    chargeback_amt = float(df[df["amount"] < 0]["amount"].sum())
    total_rows     = len(df)

    short_date = rd.strftime("%m-%d-%y")
    filename   = f"{company}_{network.replace(' ', '').replace('(', '').replace(')', '')}_{short_date}.csv"
    token      = uuid.uuid4().hex
    folder     = os.path.join(STORE_DIR, token)
    os.makedirs(folder, exist_ok=True)
    df.to_csv(os.path.join(folder, filename), index=False)
    _cleanup_old()

    return jsonify({
        "total_rows":     total_rows,
        "gross":          gross,
        "chargeback_amt": abs(chargeback_amt),
        "net":            net,
        "download_url":   f"/download/{token}",
        "filename":       filename,
        "preview":        df.head(8).to_dict(orient="records"),
    })


@app.route("/download/<token>")
def download(token):
    folder = os.path.join(STORE_DIR, os.path.basename(token))
    if not os.path.isdir(folder):
        abort(404)
    csvs = [f for f in os.listdir(folder) if f.lower().endswith(".csv")]
    if not csvs:
        abort(404)
    return send_file(
        os.path.join(folder, csvs[0]),
        mimetype="text/csv",
        as_attachment=True,
        download_name=csvs[0],
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
