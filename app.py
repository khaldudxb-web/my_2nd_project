from flask import Flask, render_template, redirect, url_for, request, session, flash
from flask_mail import Mail, Message
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import random
from dotenv import load_dotenv
from dateutil.relativedelta import relativedelta
from bson import ObjectId
import json

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = 'aviation_corp_secret_key_2025'

# Flask-Mail configuration for Gmail SMTP
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'khaldudxb@gmail.com')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', 'your_app_password_here')  # Set via environment variable
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME', 'khaldudxb@gmail.com')

mail = Mail(app)

# Helper function to send emails
def send_email(subject, recipients, body, html=None):
    msg = Message(subject, recipients=recipients, body=body, html=html)
    try:
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Email sending failed: {e}")
        return False

# MongoDB connection
client = MongoClient("mongodb+srv://khaldudxb_db_user:5zWzdlnZYrOJnXLe@mongodbcluster.clyqmaj.mongodb.net/")
db = client["Aviation"]
aviation_data = db["Aviation_Data"]
contact_messages = db["Contact_Messages"]
employees = db["Employees"]

# Seed sample employee data if not present
def seed_employees(count=100):
    existing = employees.count_documents({})
    if existing == count:
        return
    if existing > 0:
        employees.delete_many({})

    first_names = [
        "Alex", "Jordan", "Taylor", "Morgan", "Riley", "Casey", "Jamie", "Cameron", "Drew", "Reese",
        "Avery", "Quinn", "Hayden", "Rowan", "Parker", "Sydney", "Payton", "Blake", "Kendall", "Harper"
    ]
    last_names = [
        "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
        "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin"
    ]
    designations = [
        "Pilot", "Co-Pilot", "Flight Attendant", "Maintenance Engineer", "Operations Manager", "Ground Support",
        "Air Traffic Controller", "Avionics Technician", "Safety Officer", "Flight Dispatcher"
    ]
    genders = ["Male", "Female"]

    used_names = set()
    base_date = datetime.utcnow() - timedelta(days=365 * 5)

    new_employees = []
    while len(new_employees) < count:
        first = random.choice(first_names)
        last = random.choice(last_names)
        full = f"{first} {last}"
        if full in used_names:
            continue
        used_names.add(full)

        age = random.randint(23, 60)
        doj = base_date + timedelta(days=random.randint(30, 365 * 5))
        gender = random.choice(genders)
        designation = random.choice(designations)

        new_employees.append({
            "name": full,
            "designation": designation,
            "gender": gender,
            "age": age,
            "date_of_joining": doj,
        })

    employees.insert_many(new_employees)

# Create a default admin user if missing
if not aviation_data.find_one({"username": "admin"}):
    aviation_data.insert_one({
        "username": "admin",
        "email": "admin@aviationcorp.com",
        "password": generate_password_hash("admin123")
    })

seed_employees()
@app.route('/')
def index():
    return redirect(url_for('home'))

@app.route('/home')
def home():
    return render_template('home.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        message = request.form.get('message')

        contact_messages.insert_one({
            "name": name,
            "email": email,
            "message": message,
            "submitted_at": datetime.utcnow(),
            "ip_address": request.remote_addr,
            "user_agent": request.headers.get('User-Agent'),
            "status": "unread",  # unread, read, responded
            "email_sent": True
        })

        # Send email notification
        email_body = f"""
New contact form submission received:

Name: {name}
Email: {email}
Message: {message}

Submitted at: {datetime.utcnow()}
"""
        if send_email('New Contact Form Submission - Aviation Corp', ['khaldudxb@gmail.com'], email_body):
            flash('Message sent successfully! We will get back to you soon.', 'success')
        else:
            flash('Message sent successfully, but there was an issue with email notification.', 'warning')

        return redirect(url_for('contact'))

    return render_template('contact.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # Find user in database
        user = aviation_data.find_one({"username": username})

        if user and check_password_hash(user['password'], password):
            session['username'] = username
            flash('Login successful! Welcome back.', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password.', 'error')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/login-as-admin')
def login_as_admin():
    admin_user = aviation_data.find_one({"username": "admin"})
    if not admin_user:
        flash('Admin account not found.', 'error')
        return redirect(url_for('login'))

    session['username'] = 'admin'
    flash('Logged in as admin.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        # Check if user already exists
        existing_user = aviation_data.find_one({"username": username})
        if existing_user:
            flash('Username already exists. Please choose another.', 'error')
            return redirect(url_for('register'))

        existing_email = aviation_data.find_one({"email": email})
        if existing_email:
            flash('Email already registered. Please login instead.', 'error')
            return redirect(url_for('register'))

        # Hash password and save to database
        hashed_password = generate_password_hash(password)
        aviation_data.insert_one({
            "username": username,
            "email": email,
            "password": hashed_password
        })

        # Send welcome email
        welcome_body = f"""
Welcome to Aviation Corp, {username}!

Your account has been created successfully.

You can now login and access your dashboard.

Best regards,
Aviation Corp Team
"""
        send_email('Welcome to Aviation Corp!', [email], welcome_body)

        flash('Account created successfully! Please login.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        flash('Please login to access the dashboard.', 'error')
        return redirect(url_for('login'))

    # Load employees for the dashboard table
    employee_list = list(employees.find({}, {"_id": 0}).sort('name', 1))
    
    # Calculate tenure for each employee
    current_date = datetime.now()
    for emp in employee_list:
        tenure = relativedelta(current_date, emp['date_of_joining'])
        emp['tenure'] = f"{tenure.years} years, {tenure.months} months"
        emp['tenure_months'] = (tenure.years * 12) + tenure.months
        emp['year_joined'] = emp['date_of_joining'].year

    return render_template(
        'dashboard.html',
        username=session['username'],
        is_dashboard=True,
        employees=employee_list
    )

@app.route('/admin/contact-messages')
def admin_contact_messages():
    if 'username' not in session:
        flash('Please login to access admin area.', 'error')
        return redirect(url_for('login'))
    
    # Get all contact messages, sorted by newest first
    messages = list(contact_messages.find({}, {"_id": 0}).sort('submitted_at', -1))
    return render_template('admin_contact.html', messages=messages)

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
