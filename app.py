import os
import math
import random
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import pymysql
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "sfr_master_secret_key_secure_2026")

def get_db_connection():
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DB", "smart_food_rescue_db"),
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# Haversine distance formula (km)
def calculate_haversine_distance_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 2)

def get_location_coordinates(location_str):
    loc_lower = location_str.lower()
    if "palani" in loc_lower:
        return 10.3752, 77.9621
    elif "gandhigram" in loc_lower:
        return 10.3685, 77.9754
    elif "nilaiyur" in loc_lower:
        return 10.3700, 77.9900
    elif "thadikombu" in loc_lower:
        return 10.4100, 77.9500
    elif "round road" in loc_lower:
        return 10.3690, 77.9760
    return 10.3673, 77.9803

# --- FRESH FOOD MATCHING ENGINE (EXACT RULE) ---
def process_fresh_donation_matching(donation_id, donor_location, food_qty, food_category):
    conn = get_db_connection()
    try:
        d_lat, d_lng = get_location_coordinates(donor_location)
        with conn.cursor() as cursor:
            # Fetch active trusts
            cursor.execute("SELECT * FROM trusts WHERE availability_status = 'Active'")
            trusts = cursor.fetchall()
            
            for t in trusts:
                t_lat = float(t['lat'] or 10.3685)
                t_lng = float(t['lng'] or 77.9754)
                dist_km = calculate_haversine_distance_km(d_lat, d_lng, t_lat, t_lng)
                required_qty = float(t['required_kg'] or 0.0)
                accepted_cats = [c.strip().lower() for c in (t['accepted_categories'] or '').split(',')]
                
                # EXACT RULE: Distance <= 10 KM AND Trust Required Quantity <= Donated Quantity
                is_category_accepted = any(cat in food_category.lower() for cat in accepted_cats) if accepted_cats else True
                
                if dist_km <= 10.0 and required_qty <= food_qty and is_category_accepted:
                    # Notify eligible trust
                    cursor.execute("""
                        INSERT INTO trust_notifications (donation_id, trust_id, distance_km, response_status)
                        VALUES (%s, %s, %s, 'Pending')
                    """, (donation_id, t['id'], dist_km))
                    
                    cursor.execute("""
                        INSERT INTO notifications (recipient_type, recipient_id, message)
                        VALUES ('Trust', %s, %s)
                    """, (t['id'], f"New fresh food match! {food_qty} KG ({food_category}) located {dist_km} KM away."))
            conn.commit()
    finally:
        conn.close()

# --- SPOILED FOOD MATCHING ENGINE ---
def process_spoiled_donation_matching(donation_id, donor_location, food_qty, food_category):
    conn = get_db_connection()
    try:
        d_lat, d_lng = get_location_coordinates(donor_location)
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM recycling_centers WHERE availability_status = 'Active'")
            centers = cursor.fetchall()
            
            for c in centers:
                c_lat = float(c['lat'] or 10.3700)
                c_lng = float(c['lng'] or 77.9900)
                dist_km = calculate_haversine_distance_km(d_lat, d_lng, c_lat, c_lng)
                available_cap = float(c['available_capacity'] or 0.0)
                
                if dist_km <= 25.0 and available_cap >= food_qty:
                    cursor.execute("""
                        INSERT INTO recycling_notifications (donation_id, recycling_center_id, distance_km, response_status)
                        VALUES (%s, %s, %s, 'Pending')
                    """, (donation_id, c['id'], dist_km))
                    
                    cursor.execute("""
                        INSERT INTO notifications (recipient_type, recipient_id, message)
                        VALUES ('Recycler', %s, %s)
                    """, (c['id'], f"Inbound spoiled food batch ({food_qty} KG) routed to your plant facility."))
            conn.commit()
    finally:
        conn.close()

# --- PUBLIC ROUTES ---
@app.route("/")
def index():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as cnt FROM donations")
            donations_count = cursor.fetchone()['cnt']
            cursor.execute("SELECT COUNT(*) as cnt FROM trusts WHERE availability_status='Active'")
            trusts_count = cursor.fetchone()['cnt'] * 15 # Estimated people fed multiplier
            cursor.execute("SELECT COUNT(*) as cnt FROM donations WHERE status LIKE 'Bio-Recycled%%'")
            recycling_count = cursor.fetchone()['cnt']
            cursor.execute("SELECT COUNT(*) as cnt FROM marketplace_orders")
            orders_count = cursor.fetchone()['cnt']
    finally:
        conn.close()
    return render_template("index.html", donations_count=donations_count, trusts_count=trusts_count, recycling_count=recycling_count, orders_count=orders_count)

@app.route("/select_role")
def select_role():
    return render_template("select_role.html")

# --- AUTHENTICATION & REGISTRATION ---
@app.route("/register/<role>", methods=["GET", "POST"])
def register(role):
    if role in ['trust', 'recycling']:
        flash("Public self-registration for Trusts and Recycling Centres is disabled. Please contact the Admin.", "danger")
        return redirect(url_for('login', role=role))
        
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        password = request.form.get("password")
        address = request.form.get("address", "Dindigul")
        
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                if role == "donor":
                    cursor.execute("INSERT INTO donors (name, email, phone, password, address) VALUES (%s, %s, %s, %s, %s)", (name, email, phone, password, address))
                elif role == "buyer":
                    cursor.execute("INSERT INTO buyers (name, email, phone, password, address) VALUES (%s, %s, %s, %s, %s)", (name, email, phone, password, address))
                elif role == "volunteer":
                    cursor.execute("INSERT INTO volunteers (name, phone, password) VALUES (%s, %s, %s)", (name, phone, password))
            conn.commit()
            flash("Registration successful! Please login.", "success")
            return redirect(url_for("login", role=role))
        except Exception as e:
            flash(f"Registration error (Email or Phone might already exist): {e}", "danger")
        finally:
            conn.close()
    return render_template("register.html", role=role)

@app.route("/login/<role>", methods=["GET", "POST"])
def login(role):
    if request.method == "POST":
        identifier = request.form.get("identifier")
        password = request.form.get("password")
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                if role == "donor":
                    cursor.execute("SELECT * FROM donors WHERE email = %s OR phone = %s", (identifier, identifier))
                    user = cursor.fetchone()
                    if user and user['password'] == password:
                        session['donor_id'] = user['id']
                        session['donor_name'] = user['name']
                        return redirect(url_for('donor_dashboard'))
                elif role == "trust":
                    cursor.execute("SELECT * FROM trusts WHERE email = %s OR phone = %s", (identifier, identifier))
                    user = cursor.fetchone()
                    if user and user['password'] == password:
                        if user['availability_status'] != 'Active':
                            flash("Your trust account is currently inactive.", "danger")
                            return redirect(url_for('login', role='trust'))
                        session['trust_id'] = user['id']
                        session['trust_name'] = user['name']
                        return redirect(url_for('trust_dashboard'))
                elif role == "recycling":
                    cursor.execute("SELECT * FROM recycling_centers WHERE email = %s", (identifier,))
                    user = cursor.fetchone()
                    if user and user['password'] == password:
                        if user['availability_status'] != 'Active':
                            flash("Your recycling centre account is currently inactive.", "danger")
                            return redirect(url_for('login', role='recycling'))
                        session['recycler_id'] = user['id']
                        session['recycler_name'] = user['center_name']
                        return redirect(url_for('recycler_dashboard'))
                elif role == "volunteer":
                    cursor.execute("SELECT * FROM volunteers WHERE phone = %s", (identifier,))
                    user = cursor.fetchone()
                    if user and user['password'] == password:
                        session['volunteer_id'] = user['id']
                        session['volunteer_name'] = user['name']
                        return redirect(url_for('volunteer_dashboard'))
                elif role == "buyer":
                    cursor.execute("SELECT * FROM buyers WHERE email = %s OR phone = %s", (identifier, identifier))
                    user = cursor.fetchone()
                    if user and user['password'] == password:
                        session['buyer_id'] = user['id']
                        session['buyer_name'] = user['name']
                        return redirect(url_for('buyer_dashboard'))
                elif role == "admin":
                    cursor.execute("SELECT * FROM admins WHERE username = %s", (identifier,))
                    user = cursor.fetchone()
                    if user and user['password'] == password:
                        session['admin_logged_in'] = True
                        return redirect(url_for('admin_dashboard'))
            flash("Invalid credentials or role mismatch.", "danger")
        finally:
            conn.close()
    return render_template("login.html", role=role)

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("index"))

# --- DONOR MODULE ---
@app.route("/donor/dashboard")
def donor_dashboard():
    if "donor_id" not in session:
        return redirect(url_for("login", role="donor"))
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT d.*, t.name as trust_name FROM donations d LEFT JOIN trusts t ON d.accepted_trust_id = t.id WHERE d.donor_id = %s ORDER BY d.id DESC", (session['donor_id'],))
            donations = cursor.fetchall()
    finally:
        conn.close()
    total_donations = len(donations)
    active_donations = len([d for d in donations if 'Delivered' not in d['status'] and 'Bio-Recycled' not in d['status']])
    completed_donations = len([d for d in donations if 'Delivered' in d['status'] or 'Bio-Recycled' in d['status']])
    return render_template("donor_dashboard.html", donations=donations, total_donations=total_donations, active_donations=active_donations, completed_donations=completed_donations)

@app.route("/donor/donate", methods=["POST"])
def donate_food():
    if "donor_id" not in session:
        return redirect(url_for("login", role="donor"))
    food_type = request.form.get("food_type")
    quantity_kg = float(request.form.get("quantity_kg", 1.0))
    food_condition = request.form.get("food_condition", "Fresh")
    storage_condition = request.form.get("storage_condition", "Room Temperature")
    location = request.form.get("location", "Dindigul")
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            if food_condition == "Spoiled":
                cursor.execute("""
                    INSERT INTO donations (donor_id, food_type, quantity_kg, location, food_condition, storage_condition, status, recycling_status)
                    VALUES (%s, %s, %s, %s, %s, %s, 'Inbound Bio-Recovery (Awaiting Centre Acceptance)', 'Pending Center Acceptance')
                """, (session['donor_id'], food_type, quantity_kg, location, food_condition, storage_condition))
                donation_id = cursor.lastrowid
                conn.commit()
                process_spoiled_donation_matching(donation_id, location, quantity_kg, food_type)
            else:
                cursor.execute("""
                    INSERT INTO donations (donor_id, food_type, quantity_kg, location, food_condition, storage_condition, status)
                    VALUES (%s, %s, %s, %s, %s, %s, 'Pending Matching')
                """, (session['donor_id'], food_type, quantity_kg, location, food_condition, storage_condition))
                donation_id = cursor.lastrowid
                conn.commit()
                process_fresh_donation_matching(donation_id, location, quantity_kg, food_type)
    finally:
        conn.close()
    flash("Food batch successfully posted and processed through matching engine!", "success")
    return redirect(url_for("donor_dashboard"))

# --- TRUST MODULE ---
@app.route("/trust/dashboard", methods=["GET", "POST"])
def trust_dashboard():
    if "trust_id" not in session:
        return redirect(url_for("login", role="trust"))
    trust_id = session['trust_id']
    conn = get_db_connection()
    
    try:
        with conn.cursor() as cursor:
            if request.method == "POST" and "update_profile" in request.form:
                required_kg = float(request.form.get("required_kg", 50))
                accepted_cats = request.form.get("accepted_categories", "")
                cursor.execute("UPDATE trusts SET required_kg = %s, accepted_categories = %s WHERE id = %s", (required_kg, accepted_cats, trust_id))
                conn.commit()
                flash("Trust profile updated successfully!", "success")
                
            cursor.execute("SELECT * FROM trusts WHERE id = %s", (trust_id,))
            trust = cursor.fetchone()
            
            # Notifications & Claims
            cursor.execute("""
                SELECT tn.*, d.food_type, d.quantity_kg, d.location, d.food_condition, d.storage_condition, d.status as donation_status, dn.name as donor_name
                FROM trust_notifications tn
                JOIN donations d ON tn.donation_id = d.id
                JOIN donors dn ON d.donor_id = dn.id
                WHERE tn.trust_id = %s ORDER BY tn.id DESC
            """, (trust_id,))
            notifications = cursor.fetchall()
            
            cursor.execute("SELECT * FROM donations WHERE accepted_trust_id = %s ORDER BY id DESC", (trust_id,))
            my_claims = cursor.fetchall()
    finally:
        conn.close()
        
    available_notifs_count = len([n for n in notifications if n['response_status'] == 'Pending'])
    claimed_count = len([c for c in my_claims if 'Delivered' not in c['status']])
    delivered_count = len([c for c in my_claims if 'Delivered' in c['status']])
    
    return render_template("trust_dashboard.html", trust=trust, notifications=notifications, my_claims=my_claims, 
                           available_notifs_count=available_notifs_count, claimed_count=claimed_count, delivered_count=delivered_count)

@app.route("/trust/respond_notification/<int:notif_id>", methods=["POST"])
def trust_respond_notification(notif_id):
    if "trust_id" not in session:
        return redirect(url_for("login", role="trust"))
    action = request.form.get("action") # Accept or Reject
    pickup_mode = request.form.get("pickup_mode", "volunteer")
    trust_id = session['trust_id']
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM trust_notifications WHERE id = %s AND trust_id = %s", (notif_id, trust_id))
            notif = cursor.fetchone()
            if not notif or notif['response_status'] != 'Pending':
                flash("This notification is no longer active or already responded to.", "danger")
                return redirect(url_for('trust_dashboard'))
                
            donation_id = notif['donation_id']
            
            if action == "Accept":
                # ATOMIC CHECK & UPDATE: Ensure donation is still unaccepted
                cursor.execute("SELECT accepted_trust_id FROM donations WHERE id = %s FOR UPDATE", (donation_id,))
                don = cursor.fetchone()
                if don and don['accepted_trust_id'] is not None:
                    flash("Sorry! Another trust has already accepted this donation.", "danger")
                    cursor.execute("UPDATE trust_notifications SET response_status = 'Closed' WHERE id = %s", (notif_id,))
                    conn.commit()
                    return redirect(url_for('trust_dashboard'))
                    
                otp = str(random.randint(1000, 9999))
                volunteer_needed = 1 if pickup_mode == "volunteer" else 0
                status_text = 'Donation Locked (Volunteer Requested - Awaiting Admin Assignment)' if volunteer_needed else 'Donation Locked (Self-Pickup Scheduled)'
                
                # Assign selected trust
                cursor.execute("""
                    UPDATE donations SET status = %s, accepted_trust_id = %s, volunteer_needed = %s, delivery_otp = %s WHERE id = %s
                """, (status_text, trust_id, volunteer_needed, otp, donation_id))
                
                # Update this notification status to Accepted
                cursor.execute("UPDATE trust_notifications SET response_status = 'Accepted', responded_at = NOW() WHERE id = %s", (notif_id,))
                
                # Close all other notifications for this donation and notify them
                cursor.execute("UPDATE trust_notifications SET response_status = 'Closed' WHERE donation_id = %s AND id != %s", (donation_id, notif_id))
                
                conn.commit()
                flash(f"Donation successfully accepted! Handover OTP: {otp}", "success")
            else:
                cursor.execute("UPDATE trust_notifications SET response_status = 'Rejected', responded_at = NOW() WHERE id = %s", (notif_id,))
                conn.commit()
                flash("Donation offer rejected.", "info")
    finally:
        conn.close()
    return redirect(url_for("trust_dashboard"))

@app.route("/trust/verify_otp/<int:donation_id>", methods=["POST"])
def trust_verify_otp(donation_id):
    if "trust_id" not in session:
        return redirect(url_for("login", role="trust"))
    entered_otp = request.form.get("otp")
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM donations WHERE id = %s AND accepted_trust_id = %s", (donation_id, session['trust_id']))
            donation = cursor.fetchone()
            
            if donation and donation['delivery_otp'] == entered_otp:
                cursor.execute("UPDATE donations SET status = 'Delivered & Completed' WHERE id = %s", (donation_id,))
                conn.commit()
                flash("OTP verified successfully! Delivery completed.", "success")
            else:
                flash("Invalid OTP code!", "danger")
    finally:
        conn.close()
    return redirect(url_for("trust_dashboard"))

# --- RECYCLING MODULE ---
@app.route("/recycling/dashboard", methods=["GET", "POST"])
def recycler_dashboard():
    if "recycler_id" not in session:
        return redirect(url_for("login", role="recycling"))
    recycler_id = session['recycler_id']
    conn = get_db_connection()
    
    try:
        with conn.cursor() as cursor:
            if request.method == "POST" and "toggle_status" in request.form:
                new_status = request.form.get("availability_status")
                cursor.execute("UPDATE recycling_centers SET availability_status = %s WHERE id = %s", (new_status, recycler_id))
                conn.commit()
                flash("Plant operational status updated!", "success")
                
            cursor.execute("SELECT * FROM recycling_centers WHERE id = %s", (recycler_id,))
            center = cursor.fetchone()
            
            cursor.execute("""
                SELECT rn.*, d.food_type, d.quantity_kg, d.location, d.food_condition, d.status as donation_status, dn.name as donor_name
                FROM recycling_notifications rn
                JOIN donations d ON rn.donation_id = d.id
                JOIN donors dn ON d.donor_id = dn.id
                WHERE rn.recycling_center_id = %s ORDER BY rn.id DESC
            """, (recycler_id,))
            waste_batches = cursor.fetchall()
            
            cursor.execute("SELECT * FROM products WHERE recycler_id = %s", (recycler_id,))
            products = cursor.fetchall()
            
            cursor.execute("SELECT * FROM notifications WHERE recipient_type = 'Recycler' AND recipient_id = %s ORDER BY id DESC", (recycler_id,))
            notifications = cursor.fetchall()
    finally:
        conn.close()
        
    pending_count = len([w for w in waste_batches if w['response_status'] == 'Pending'])
    accepted_count = len([w for w in waste_batches if w['response_status'] == 'Accepted'])
    
    return render_template("recycler_dashboard.html", center=center, waste_batches=waste_batches, products=products, notifications=notifications,
                           pending_count=pending_count, accepted_count=accepted_count)

@app.route("/recycling/respond_batch/<int:notif_id>", methods=["POST"])
def recycling_respond_batch(notif_id):
    if "recycler_id" not in session:
        return redirect(url_for("login", role="recycling"))
    action = request.form.get("action")
    recycler_id = session['recycler_id']
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM recycling_notifications WHERE id = %s AND recycling_center_id = %s", (notif_id, recycler_id))
            notif = cursor.fetchone()
            if not notif or notif['response_status'] != 'Pending':
                flash("Batch notification expired or already handled.", "danger")
                return redirect(url_for('recycler_dashboard'))
                
            donation_id = notif['donation_id']
            if action == "Accept":
                cursor.execute("SELECT recycling_center_id FROM donations WHERE id = %s FOR UPDATE", (donation_id,))
                don = cursor.fetchone()
                if don and don['recycling_center_id'] is not None:
                    flash("Another centre has already accepted this batch.", "danger")
                    cursor.execute("UPDATE recycling_notifications SET response_status = 'Closed' WHERE id = %s", (notif_id,))
                    conn.commit()
                    return redirect(url_for('recycler_dashboard'))
                    
                otp = str(random.randint(1000, 9999))
                cursor.execute("""
                    UPDATE donations SET recycling_center_id = %s, status = 'Bio-Recovery Locked (Volunteer Requested)', recycling_status = 'Accepted by Plant - Awaiting Volunteer', volunteer_needed = 1, delivery_otp = %s WHERE id = %s
                """, (recycler_id, otp, donation_id))
                
                cursor.execute("UPDATE recycling_notifications SET response_status = 'Accepted', responded_at = NOW() WHERE id = %s", (notif_id,))
                cursor.execute("UPDATE recycling_notifications SET response_status = 'Closed' WHERE donation_id = %s AND id != %s", (donation_id, notif_id))
                conn.commit()
                flash(f"Batch accepted successfully! Plant Handover OTP: {otp}", "success")
            else:
                cursor.execute("UPDATE recycling_notifications SET response_status = 'Rejected', responded_at = NOW() WHERE id = %s", (notif_id,))
                conn.commit()
                flash("Waste batch request declined.", "info")
    finally:
        conn.close()
    return redirect(url_for("recycler_dashboard"))

@app.route("/recycling/create_product", methods=["POST"])
def create_product():
    if "recycler_id" not in session:
        return redirect(url_for("login", role="recycling"))
    product_name = request.form.get("product_name")
    description = request.form.get("description")
    price = float(request.form.get("price"))
    quantity = int(request.form.get("quantity"))
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("INSERT INTO products (recycler_id, product_name, description, price, quantity) VALUES (%s, %s, %s, %s, %s)",
                         (session['recycler_id'], product_name, description, price, quantity))
        conn.commit()
    finally:
        conn.close()
    flash("Green Marketplace fertilizer product published!", "success")
    return redirect(url_for("recycler_dashboard"))

# --- VOLUNTEER MODULE (ADMIN-MANAGED ASSIGNMENTS) ---
@app.route("/volunteer/dashboard")
def volunteer_dashboard():
    if "volunteer_id" not in session:
        return redirect(url_for("login", role="volunteer"))
    volunteer_id = session['volunteer_id']
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM volunteers WHERE id = %s", (volunteer_id,))
            volunteer = cursor.fetchone()
            
            # Volunteers only view tasks assigned specifically to them by Admin
            cursor.execute("""
                SELECT d.*, dn.name as donor_name, t.name as trust_name, t.location as trust_loc 
                FROM donations d 
                JOIN donors dn ON d.donor_id = dn.id 
                LEFT JOIN trusts t ON d.accepted_trust_id = t.id 
                WHERE d.volunteer_id = %s ORDER BY d.id DESC
            """, (volunteer_id,))
            tasks = cursor.fetchall()
            
            cursor.execute("SELECT COUNT(*) as cnt FROM donations WHERE volunteer_id = %s AND status LIKE 'Delivered%%'", (volunteer_id,))
            completed_tasks = cursor.fetchone()['cnt']
    finally:
        conn.close()
        
    assigned_tasks = len([t for t in tasks if 'Delivered' not in t['status']])
    return render_template("volunteer_dashboard.html", volunteer=volunteer, tasks=tasks, assigned_tasks=assigned_tasks, completed_tasks=completed_tasks)

@app.route("/volunteer/respond_task/<int:donation_id>", methods=["POST"])
def volunteer_respond_task(donation_id):
    if "volunteer_id" not in session:
        return redirect(url_for("login", role="volunteer"))
    action = request.form.get("action") # Accept or Decline
    volunteer_id = session['volunteer_id']
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM donations WHERE id = %s AND volunteer_id = %s", (donation_id, volunteer_id))
            task = cursor.fetchone()
            if not task:
                flash("Unauthorized task action.", "danger")
                return redirect(url_for('volunteer_dashboard'))
                
            if action == "Accept":
                cursor.execute("UPDATE donations SET volunteer_status = 'Accepted', status = 'In Transit (Volunteer En Route)' WHERE id = %s", (donation_id,))
                flash("Task accepted! You are en route.", "success")
            else:
                # Return task to admin for reassignment
                cursor.execute("UPDATE donations SET volunteer_id = NULL, volunteer_status = 'None', status = 'Pending Volunteer Assignment' WHERE id = %s", (donation_id,))
                flash("Task declined and returned to Admin for reassignment.", "info")
        conn.commit()
    finally:
        conn.close()
    return redirect(url_for("volunteer_dashboard"))

@app.route("/volunteer/verify_otp/<int:donation_id>", methods=["POST"])
def volunteer_verify_otp(donation_id):
    if "volunteer_id" not in session:
        return redirect(url_for("login", role="volunteer"))
    entered_otp = request.form.get("otp")
    volunteer_id = session['volunteer_id']
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM donations WHERE id = %s AND volunteer_id = %s", (donation_id, volunteer_id))
            donation = cursor.fetchone()
            
            if donation and donation['delivery_otp'] == entered_otp:
                cursor.execute("UPDATE donations SET status = 'Delivered & Completed' WHERE id = %s", (donation_id,))
                cursor.execute("UPDATE volunteers SET task_status = 'Available' WHERE id = %s", (volunteer_id,))
                conn.commit()
                flash("Handover OTP verified successfully! Delivery completed.", "success")
            else:
                flash("Incorrect OTP code!", "danger")
    finally:
        conn.close()
    return redirect(url_for("volunteer_dashboard"))

@app.route("/api/volunteer/update_gps", methods=["POST"])
def update_gps():
    if "volunteer_id" not in session:
        return jsonify({"status": "unauthorized"}), 401
    data = request.json
    lat = data.get("lat")
    lng = data.get("lng")
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE volunteers SET current_lat = %s, current_lng = %s WHERE id = %s", (lat, lng, session['volunteer_id']))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "success"})

# --- MARKETPLACE & BUYER MODULE ---
@app.route("/marketplace")
def marketplace():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT p.*, rc.center_name FROM products p JOIN recycling_centers rc ON p.recycler_id = rc.id WHERE p.quantity > 0")
            products = cursor.fetchall()
    finally:
        conn.close()
    return render_template("marketplace.html", products=products)

@app.route("/buyer/dashboard")
def buyer_dashboard():
    if "buyer_id" not in session:
        return redirect(url_for("login", role="buyer"))
    buyer_id = session['buyer_id']
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM buyers WHERE id = %s", (buyer_id,))
            buyer = cursor.fetchone()
            cursor.execute("SELECT p.*, rc.center_name FROM products p JOIN recycling_centers rc ON p.recycler_id = rc.id WHERE p.quantity > 0")
            products = cursor.fetchall()
            cursor.execute("SELECT mo.*, p.product_name, rc.center_name FROM marketplace_orders mo JOIN products p ON mo.product_id = p.id JOIN recycling_centers rc ON mo.recycler_id = rc.id WHERE mo.buyer_id = %s ORDER BY mo.id DESC", (buyer_id,))
            orders = cursor.fetchall()
    finally:
        conn.close()
    return render_template("buyer_dashboard.html", buyer=buyer, products=products, orders=orders)

@app.route("/buyer/checkout/<int:product_id>", methods=["POST"])
def buyer_checkout(product_id):
    if "buyer_id" not in session:
        return redirect(url_for("login", role="buyer"))
    qty = int(request.form.get("quantity", 1))
    address = request.form.get("delivery_address", "Dindigul")
    phone = request.form.get("buyer_phone", "")
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM products WHERE id = %s", (product_id,))
            prod = cursor.fetchone()
            if prod and prod['quantity'] >= qty:
                total_price = prod['price'] * qty
                cursor.execute("""
                    INSERT INTO marketplace_orders (buyer_id, product_id, recycler_id, order_qty, total_price, delivery_address, buyer_phone, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'Order Placed (Awaiting Plant Dispatch)')
                """, (session['buyer_id'], product_id, prod['recycler_id'], qty, total_price, address, phone))
                cursor.execute("UPDATE products SET quantity = quantity - %s WHERE id = %s", (qty, product_id))
                conn.commit()
                flash("Order placed successfully on Green Marketplace!", "success")
            else:
                flash("Insufficient stock available!", "danger")
    finally:
        conn.close()
    return redirect(url_for("buyer_dashboard"))

# --- ADMIN COMMAND CENTER & MANAGEMENT MODULE ---
@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get("admin_logged_in"):
        return redirect(url_for("login", role="admin"))
    conn = get_db_connection()
    
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as cnt FROM donors")
            d_cnt = cursor.fetchone()['cnt']
            cursor.execute("SELECT COUNT(*) as cnt FROM trusts")
            t_cnt = cursor.fetchone()['cnt']
            cursor.execute("SELECT COUNT(*) as cnt FROM volunteers")
            v_cnt = cursor.fetchone()['cnt']
            cursor.execute("SELECT COUNT(*) as cnt FROM buyers")
            b_cnt = cursor.fetchone()['cnt']
            total_users = d_cnt + t_cnt + v_cnt + b_cnt
            
            cursor.execute("SELECT COUNT(*) as cnt FROM donations")
            total_donations = cursor.fetchone()['cnt']
            cursor.execute("SELECT SUM(quantity_kg) as sm FROM donations WHERE food_condition = 'Spoiled'")
            res_sm = cursor.fetchone()['sm']
            recycled_waste = res_sm if res_sm else 0.0
            
            cursor.execute("SELECT COUNT(*) as cnt FROM marketplace_orders")
            orders_count = cursor.fetchone()['cnt']
            
            cursor.execute("""
                SELECT d.*, dn.name as donor_name, t.name as trust_name, rc.center_name 
                FROM donations d 
                JOIN donors dn ON d.donor_id = dn.id 
                LEFT JOIN trusts t ON d.accepted_trust_id = t.id 
                LEFT JOIN recycling_centers rc ON d.recycling_center_id = rc.id 
                ORDER BY d.id DESC
            """)
            donations = cursor.fetchall()
            
            cursor.execute("SELECT * FROM trusts")
            trusts = cursor.fetchall()
            
            cursor.execute("SELECT * FROM recycling_centers")
            recycling_centers = cursor.fetchall()
            
            cursor.execute("SELECT * FROM volunteers")
            volunteers = cursor.fetchall()
    finally:
        conn.close()
        
    return render_template("admin_dashboard.html", total_users=total_users, total_donations=total_donations, recycled_waste=recycled_waste,
                           orders_count=orders_count, donations=donations, trusts=trusts, recycling_centers=recycling_centers, volunteers=volunteers)

# Admin Trust Management Routes
@app.route("/admin/trust/add", methods=["POST"])
def admin_add_trust():
    if not session.get("admin_logged_in"):
        return redirect(url_for("login", role="admin"))
    name = request.form.get("name")
    email = request.form.get("email")
    phone = request.form.get("phone")
    password = request.form.get("password")
    location = request.form.get("location")
    req_kg = float(request.form.get("required_kg", 50))
    cats = request.form.get("accepted_categories", "Veg Meals,Non-Veg")
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO trusts (name, email, phone, password, location, required_kg, accepted_categories)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (name, email, phone, password, location, req_kg, cats))
        conn.commit()
        flash("Trust successfully created and login credentials generated!", "success")
    except Exception as e:
        flash(f"Error creating trust account: {e}", "danger")
    finally:
        conn.close()
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/trust/toggle/<int:trust_id>", methods=["POST"])
def admin_toggle_trust(trust_id):
    if not session.get("admin_logged_in"):
        return redirect(url_for("login", role="admin"))
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT availability_status FROM trusts WHERE id = %s", (trust_id,))
            t = cursor.fetchone()
            new_status = "Inactive" if t['availability_status'] == "Active" else "Active"
            cursor.execute("UPDATE trusts SET availability_status = %s WHERE id = %s", (new_status, trust_id))
        conn.commit()
        flash("Trust availability status toggled.", "success")
    finally:
        conn.close()
    return redirect(url_for("admin_dashboard"))

# Admin Recycling Centre Management Routes
@app.route("/admin/recycling/add", methods=["POST"])
def admin_add_recycling():
    if not session.get("admin_logged_in"):
        return redirect(url_for("login", role="admin"))
    name = request.form.get("center_name")
    email = request.form.get("email")
    phone = request.form.get("contact_phone")
    password = request.form.get("password")
    location = request.form.get("location")
    cap = float(request.form.get("supported_qty", 500))
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO recycling_centers (center_name, email, password, location, contact_phone, supported_qty, available_capacity)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (name, email, password, location, phone, cap, cap))
        conn.commit()
        flash("Recycling Centre created successfully!", "success")
    except Exception as e:
        flash(f"Error adding recycling centre: {e}", "danger")
    finally:
        conn.close()
    return redirect(url_for("admin_dashboard"))

# Admin-Only Volunteer Assignment
@app.route("/admin/assign_volunteer/<int:donation_id>", methods=["POST"])
def admin_assign_volunteer(donation_id):
    if not session.get("admin_logged_in"):
        return redirect(url_for("login", role="admin"))
    volunteer_id = request.form.get("volunteer_id")
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE donations SET volunteer_id = %s, volunteer_status = 'Assigned', status = 'Volunteer Assigned (Awaiting Acceptance)' WHERE id = %s
            """, (volunteer_id, donation_id))
            cursor.execute("UPDATE volunteers SET task_status = 'Assigned' WHERE id = %s", (volunteer_id,))
            conn.commit()
            flash("Volunteer successfully assigned to donation task!", "success")
    finally:
        conn.close()
    return redirect(url_for("admin_dashboard"))

@app.route("/api/admin/live_volunteer_locations")
def live_volunteer_locations():
    if not session.get("admin_logged_in"):
        return jsonify([])
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, name, current_lat, current_lng, task_status FROM volunteers")
            volunteers = cursor.fetchall()
    finally:
        conn.close()
    return jsonify(volunteers)

if __name__ == "__main__":
    app.run(debug=True, port=5000)