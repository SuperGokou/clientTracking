import os
from flask import Flask, render_template, request, flash, redirect, url_for, session, send_file, jsonify
import random
import io
import requests
from bson.objectid import ObjectId
from dotenv import load_dotenv
import certifi
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from PIL import Image, ImageDraw, ImageFont


load_dotenv()

app = Flask(__name__)

# --- CONFIGURATION ---
app.secret_key = os.getenv("SECRET_KEY")
MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI or not app.secret_key:
    print("⚠️ WARNING: Environment variables missing. Check .env")

# --- MONGODB CONNECTION ---
try:
    # Adding tlsCAFile=certifi.where() fixes SSL errors on some deployments
    client = MongoClient(MONGO_URI, server_api=ServerApi('1'), tlsCAFile=certifi.where())
    db = client['tracking_db']
    client.admin.command('ping')
    print("✅ Connected to MongoDB successfully!")
except Exception as e:
    print(f"❌ MongoDB Connection Error: {e}")
    db = None


# --- SCRAPER (Refined) ---
def scrape_junan_status(tracking_number, phone_number):
    url = "https://www.junanex.com/tracking"
    payload = {
        't': 'query_code',
        'code': tracking_number,
        'mobile': phone_number
    }
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'X-Requested-With': 'XMLHttpRequest'
        }
        response = requests.post(url, data=payload, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                history_list = data.get('message', [])
                if history_list:
                    # Logic: Get the latest entry
                    latest_entry = history_list[0]

                    # If it's a dict like {"Status": "Time"}, return the Key (Status)
                    # If it's {"Time": "Status"}, we might need the Value.
                    # Usually JunAn structure implies the Key is the description.
                    if isinstance(latest_entry, dict):
                        keys = list(latest_entry.keys())
                        if keys:
                            return keys[-1]  # Takes the last key found

            return "无相关信息 (No Info)"
        return f"Connection Failed ({response.status_code})"
    except Exception as e:
        print(f"Scraper Error: {e}")
        return "Update Failed"


# --- API: LIVE UPDATE ---
@app.route('/api/update_status/<shipment_id>')
def api_update_status(shipment_id):
    try:
        oid = ObjectId(shipment_id)

        # 1. FIX: Search in 'outgoing_shipments', not 'orders'
        shipment = db.outgoing_shipments.find_one({'_id': oid})

        if shipment:
            # 2. FIX: Get phone from the shipment itself first, or fallback to customer
            # (In your redesign, we saved 'phone' directly into the shipment to make it faster)
            phone = shipment.get('phone')

            if not phone:
                # Fallback: Look up customer if phone is missing in shipment
                customer = db.customers.find_one({'_id': shipment['customer_id']})
                phone = customer['phone'] if customer else ""

            # Run Scraper
            new_status = scrape_junan_status(shipment['tracking_number'], phone)

            # 3. FIX: Update 'outgoing_shipments'
            db.outgoing_shipments.update_one({'_id': oid}, {'$set': {'status': new_status}})

            return jsonify({'status': new_status, 'id': str(shipment_id)})

        return jsonify({'error': 'Shipment not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# --- ROUTES ---
@app.route('/captcha')
def get_captcha():
    code = str(random.randint(1000, 9999))
    session['captcha_code'] = code
    image = Image.new('RGB', (120, 40), color=(240, 240, 240))
    draw = ImageDraw.Draw(image)
    for _ in range(5):
        draw.line([(random.randint(0, 120), random.randint(0, 40)), (random.randint(0, 120), random.randint(0, 40))],
                  fill=(200, 200, 200), width=1)
    try:
        font = ImageFont.truetype("arial.ttf", 28)
    except IOError:
        font = ImageFont.load_default()
    draw.text((35, 5), code, fill=(50, 50, 50), font=font)
    img_io = io.BytesIO()
    image.save(img_io, 'PNG')
    img_io.seek(0)
    return send_file(img_io, mimetype='image/png')


@app.route('/', methods=('GET', 'POST'))
def index():
    if request.method == 'POST':
        name = request.form['name'].strip()
        phone = request.form['phone'].strip()
        user_code = request.form['code'].strip()

        real_code = session.get('captcha_code')
        if not real_code or user_code != real_code:
            flash('❌ Incorrect Verification Code (验证码错误)')
            return render_template('login.html')

        # Find Customer
        user = db.customers.find_one({'name': name, 'phone': phone})

        if user:
            return redirect(url_for('dashboard', user_id=str(user['_id'])))
        else:
            flash('❌ No records found. check Name/Phone.')

    return render_template('login.html')


@app.route('/dashboard/<user_id>')
def dashboard(user_id):
    try:
        uid = ObjectId(user_id)
        user = db.customers.find_one({'_id': uid})

        # 4. FIX: Query 'outgoing_shipments' instead of 'orders'
        # In the redesign, we linked them via 'customer_id'
        orders = list(db.outgoing_shipments.find({'customer_id': uid}))

        if user is None: return redirect(url_for('index'))

        return render_template('dashboard.html', user=user, orders=orders)
    except Exception as e:
        print(f"Dashboard Error: {e}")
        return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)