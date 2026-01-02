from flask import Flask, render_template, request, redirect
import json, os, requests, threading, time
from datetime import datetime, timedelta
from twilio.rest import Client

app = Flask(__name__)

DVLA_API_KEY = "u9NyQyYxxb1P2Vf13NyIl2szdEBU2gLW4A4YVBzx"
TWILIO_SID = "ACad58ab1285303f71a38993a38773314f"
TWILIO_TOKEN = "dc337abc1c4607b1cba8ee90e74b05ba"

BASE = os.path.dirname(__file__)
DATA = os.path.join(BASE, "data")
os.makedirs(DATA, exist_ok=True)

DB_FILE = os.path.join(DATA, "vehicles.json")
CACHE_FILE = os.path.join(DATA, "dvla_cache.json")

def load_db():
    return json.load(open(DB_FILE)) if os.path.exists(DB_FILE) else []

def save_db(data):
    json.dump(data, open(DB_FILE, "w"), indent=2)

def load_cache():
    return json.load(open(CACHE_FILE)) if os.path.exists(CACHE_FILE) else {}

def save_cache(data):
    json.dump(data, open(CACHE_FILE, "w"), indent=2)

def uk(d):
    return datetime.fromisoformat(d).strftime("%d/%m/%Y") if d else "None"

def get_dvla(reg):
    cache = load_cache()
    today = str(datetime.today().date())

    if reg in cache and cache[reg]["date"] == today:
        return cache[reg]["data"]

    url = "https://driver-vehicle-licensing.api.gov.uk/vehicle-enquiry/v1/vehicles"
    headers = {"x-api-key": DVLA_API_KEY, "Content-Type": "application/json"}
    data = requests.post(url, headers=headers, json={"registrationNumber": reg}).json()

    cache[reg] = {"date": today, "data": data}
    save_cache(cache)
    return data

def send_whatsapp(phone, msg):
    Client(TWILIO_SID, TWILIO_TOKEN).messages.create(
        from_="whatsapp:+14155238886",
        to=f"whatsapp:{phone}",
        body=msg
    )

def daily_check():
    for v in load_db():
        try:
            d = get_dvla(v["reg"])
            today = datetime.today().date()
            alert = today + timedelta(days=30)

            if d.get("motExpiryDate") and datetime.fromisoformat(d["motExpiryDate"]).date() == alert:
                send_whatsapp(v["phone"], f"Hi {v['owner']}, MOT for {v['reg']} expires on {uk(d['motExpiryDate'])}.")
            if d.get("taxDueDate") and datetime.fromisoformat(d["taxDueDate"]).date() == alert:
                send_whatsapp(v["phone"], f"Hi {v['owner']}, Road Tax for {v['reg']} expires on {uk(d['taxDueDate'])}.")
        except:
            pass

def scheduler():
    while True:
        daily_check()
        time.sleep(86400)

@app.route("/", methods=["GET","POST"])
def index():
    vehicles = load_db()
    today = datetime.today().date()
    display = []

    for i,v in enumerate(vehicles, start=1):
        try:
            d = get_dvla(v["reg"])
            mot = datetime.fromisoformat(d["motExpiryDate"]).date() if d.get("motExpiryDate") else None
            tax = datetime.fromisoformat(d["taxDueDate"]).date() if d.get("taxDueDate") else None

            days = min((mot-today).days if mot else 9999,(tax-today).days if tax else 9999)

            display.append({
                "n": i,
                "owner": v["owner"],
                "reg": v["reg"],
                "phone": v["phone"],
                "make": d.get("make",""),
                "colour": d.get("colour",""),
                "mot": uk(d.get("motExpiryDate")),
                "tax": uk(d.get("taxDueDate")),
                "days": days
            })
        except:
            display.append({"n":i,**v,"make":"","colour":"","mot":"None","tax":"None","days":9999})

    display.sort(key=lambda x:x["days"])

    if request.method == "POST":
        vehicles.append({
            "owner": request.form["owner"],
            "reg": request.form["reg"].upper(),
            "phone": request.form["phone"]
        })
        save_db(vehicles)
        return redirect("/")

    return render_template("index.html", vehicles=display)

if __name__ == "__main__":
    threading.Thread(target=scheduler, daemon=True).start()
    app.run(debug=True)
