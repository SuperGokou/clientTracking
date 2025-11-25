import os
from flask import Flask, render_template, request, flash, redirect, url_for, session, send_file, jsonify
import random
import io
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
from pymongo import MongoClient
from bson.objectid import ObjectId

load_dotenv()

app = Flask(__name__)

# --- 2. USE os.getenv SAFELY ---
app.secret_key = os.getenv("SECRET_KEY")
MONGO_URI = os.getenv("MONGO_URI")


if not MONGO_URI or not app.secret_key:
    print("⚠️ WARNING: Environment variables not found. Check .env or Render Settings.")


try:
    # NEW: Using certifi to provide valid certificates
    client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
    db = client['tracking_db']
    
    # Force a connection check immediately to see if it fails here
    client.admin.command('ping')
    print("✅ Connected to MongoDB successfully!")
except Exception as e:
    print(f"❌ MongoDB Connection Error: {e}")


# --- SCRAPER ---
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
        # Use POST to talk to the API
        response = requests.post(url, data=payload, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                history_list = data.get('message', [])
                if history_list:
                    latest_entry = history_list[0]
                    # Get the last key (latest status)
                    statuses = list(latest_entry.keys())
                    if statuses:
                        return statuses[-1]
            return "无相关信息 (No Info)"
        return "Connection Failed"
    except Exception as e:
        print(f"Scraper Error: {e}")
        return "Update Failed"


# --- API: LIVE UPDATE ---
@app.route('/api/update_status/<order_id>')
def api_update_status(order_id):
    try:
        # Convert string ID to ObjectId for MongoDB lookup
        oid = ObjectId(order_id)
        order = db.orders.find_one({'_id': oid})

        if order:
            # Get Customer Phone
            customer = db.customers.find_one({'_id': order['customer_id']})
            phone = customer['phone'] if customer else ""

            # Run Scraper
            new_status = scrape_junan_status(order['tracking_number'], phone)

            # Save to MongoDB
            db.orders.update_one({'_id': oid}, {'$set': {'status': new_status}})

            return jsonify({'status': new_status, 'id': str(order_id)})

        return jsonify({'error': 'Order not found'}), 404
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

        # MongoDB Query
        user = db.customers.find_one({'name': name, 'phone': phone})

        if user:
            # Convert ObjectId to string for URL
            return redirect(url_for('dashboard', user_id=str(user['_id'])))
        else:
            flash('❌ No order found for this Name/Phone.')

    return render_template('login.html')


@app.route('/dashboard/<user_id>')
def dashboard(user_id):
    try:
        uid = ObjectId(user_id)
        user = db.customers.find_one({'_id': uid})
        orders = list(db.orders.find({'customer_id': uid}))

        if user is None: return redirect(url_for('index'))

        return render_template('dashboard.html', user=user, orders=orders)
    except:
        return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)