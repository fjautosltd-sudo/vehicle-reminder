from flask import Flask, render_template, request, redirect
import json, os, requests, threading, time
from datetime import datetime, timedelta
from twilio.rest import Client

app = Flask(__name__)

DVLA_API_KEY = "u9NyQyYxxb1P2Vf13NyIl2szdEBU2gLW4A4YVBzx"
TWILIO_SID = "ACad58ab1285303f71a38993a38773314f"
TWILIO_TOKEN = "dc337abc1c4607b1cba8ee90e74b05ba"

DATA_FOLDER = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_FOLDER, exist_ok=True)
DB_FILE = os.path.join(DATA_FOLDER, "vehicles.json")

def load_db():
    if not os.path.exists(DB_FILE):
        return []
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def get_dvla(reg):
    url = "https://driver-vehicle-licensing.api.gov.uk/vehicle-enquiry/v1/vehicles"
    headers = {"x-api-key": DVLA_API_KEY, "Content-Type": "application/json"}
    return requests.post(url, headers=headers, json={"registrationNumber": reg}).json()

def send_whatsapp(phone, msg):
    Client(TWILIO_SID, TWILIO_TOKEN).messages.create(
        from_="whatsapp:+14155238886",
        to=f"whatsapp:{phone}",
        body=msg
    )

def daily_check():
    for v in load_db():
        try:
            data = get_dvla(v["reg"])
            today = datetime.today().date()
            alert = today + timedelta(days=30)

            if data.get("motExpiryDate") and datetime.fromisoformat(data["motExpiryDate"]).date() == alert:
                send_whatsapp(v["phone"], f"Hi {v['owner']}, MOT for {v['reg']} expires on {data['motExpiryDate']}.")

            if data.get("taxDueDate") and datetime.fromisoformat(data["taxDueDate"]).date() == alert:
                send_whatsapp(v["phone"], f"Hi {v['owner']}, Road Tax for {v['reg']} expires on {data['taxDueDate']}.")
        except:
            pass

def scheduler():
    while True:
        daily_check()
        time.sleep(86400)

@app.route("/", methods=["GET","POST"])
def index():
    vehicles = load_db()
    display = []
    today = datetime.today().date()

    for v in vehicles:
        try:
            data = get_dvla(v["reg"])
            mot_raw = data.get("motExpiryDate")
            tax_raw = data.get("taxDueDate")

            mot = datetime.fromisoformat(mot_raw).date() if mot_raw else None
            tax = datetime.fromisoformat(tax_raw).date() if tax_raw else None

            days_left = min(
                (mot - today).days if mot else 9999,
                (tax - today).days if tax else 9999
            )

            display.append({
                "owner": v["owner"],
                "reg": v["reg"],
                "phone": v["phone"],
                "make": data.get("make",""),
                "model": data.get("model",""),
                "colour": data.get("colour",""),
                "mot": mot_raw,
                "tax": tax_raw,
                "days": days_left
            })
        except:
            display.append({**v, "make":"","model":"","colour":"","mot":"Unavailable","tax":"Unavailable","days":9999})

    display.sort(key=lambda x: x["days"])

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
