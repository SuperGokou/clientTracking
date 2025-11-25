from flask import Flask, render_template, request, flash, redirect, url_for, session, send_file
import sqlite3
import random
import io
from PIL import Image, ImageDraw, ImageFont  # Ensure Pillow is installed: pip install Pillow

app = Flask(__name__)
app.secret_key = 'super_secret_key'


def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn


# --- 1. CAPTCHA GENERATOR ---
@app.route('/captcha')
def get_captcha():
    # 1. Generate 4 random digits
    code = str(random.randint(1000, 9999))
    session['captcha_code'] = code

    # 2. Create Image
    image = Image.new('RGB', (120, 40), color=(240, 240, 240))

    # 3. Create the Drawing Tool (This is where your error likely was)
    draw = ImageDraw.Draw(image)

    # 4. Add Noise (Optional security lines)
    for _ in range(5):
        x1 = random.randint(0, 120)
        y1 = random.randint(0, 40)
        x2 = random.randint(0, 120)
        y2 = random.randint(0, 40)
        draw.line([(x1, y1), (x2, y2)], fill=(200, 200, 200), width=1)

    # 5. Draw the Text
    try:
        font = ImageFont.truetype("arial.ttf", 28)
    except IOError:
        font = ImageFont.load_default()

    # Position the text roughly in the center
    draw.text((35, 5), code, fill=(50, 50, 50), font=font)

    # 6. Return Image
    img_io = io.BytesIO()
    image.save(img_io, 'PNG')
    img_io.seek(0)
    return send_file(img_io, mimetype='image/png')


# --- 2. LOGIN PAGE ---
@app.route('/', methods=('GET', 'POST'))
def index():
    if request.method == 'POST':
        name = request.form['name'].strip()
        phone = request.form['phone'].strip()
        user_code = request.form['code'].strip()

        # Check CAPTCHA
        real_code = session.get('captcha_code')
        if not real_code or user_code != real_code:
            flash('❌ Incorrect Verification Code (验证码错误)')
            return render_template('login.html')

        # Check Database
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM customers WHERE name = ? AND phone = ?',
                            (name, phone)).fetchone()
        conn.close()

        if user:
            return redirect(url_for('dashboard', user_id=user['id']))
        else:
            flash('❌ No order found for this Name/Phone.')

    return render_template('login.html')


# --- 3. DASHBOARD ---
@app.route('/dashboard/<int:user_id>')
def dashboard(user_id):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM customers WHERE id = ?', (user_id,)).fetchone()
    orders = conn.execute('SELECT * FROM orders WHERE customer_id = ?', (user_id,)).fetchall()
    conn.close()

    if user is None:
        return redirect(url_for('index'))

    return render_template('dashboard.html', user=user, orders=orders)


if __name__ == '__main__':
    app.run(debug=True)