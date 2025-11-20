import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
import pymysql
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime # Import datetime
import pytz # Import pytz for timezone conversion

# --- FLASK APP INITIALIZATION ---
app = Flask(__name__)
app.secret_key = os.urandom(24)

# --- DATABASE CONFIGURATION ---
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'YourPasswordHere',
    'database': 'simple_bank_db',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

def get_db_connection():
    return pymysql.connect(**DB_CONFIG)

# --- DECORATORS ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def manager_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'manager_loggedin' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('manager_login'))
        return f(*args, **kwargs)
    return decorated_function

# --- GENERAL ROUTES ---
@app.route('/')
def index():
    return render_template('index.html')

# --- USER ROUTES ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        account_number = request.form['account_number']
        password = request.form['password']
        
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT u.user_id, u.first_name, u.last_name, u.password_hash, u.status,
                           a.account_id, a.account_number
                    FROM users u JOIN accounts a ON u.user_id = a.user_id
                    WHERE a.account_number = %s
                """, (account_number,))
                user = cursor.fetchone()

            if user and check_password_hash(user['password_hash'], password):
                if user['status'] == 'Inactive':
                    flash('Your account is deactivated. Please contact the bank.', 'error')
                    return redirect(url_for('login'))
                
                session['user_id'] = user['user_id']
                session['account_id'] = user['account_id']
                session['user_name'] = f"{user['first_name']} {user['last_name']}"
                session['account_number'] = user['account_number'] 
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid account number or password.', 'error')
        except pymysql.MySQLError as e:
            flash(f'Database error: {e}', 'error')
        finally:
            conn.close()
            
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT u.first_name, u.last_name, u.phone_number,
                       a.account_number, a.balance
                FROM users u JOIN accounts a ON u.user_id = a.user_id
                WHERE u.user_id = %s
            """, (session['user_id'],))
            account_details = cursor.fetchone()

            cursor.execute(
                "SELECT * FROM transactions WHERE account_id = %s ORDER BY timestamp DESC LIMIT 5",
                (session['account_id'],)
            )
            transactions_utc = cursor.fetchall()
            
            # Convert timestamps to IST
            transactions = []
            utc_tz = pytz.utc
            ist_tz = pytz.timezone('Asia/Kolkata')
            for tx in transactions_utc:
                # Make the naive datetime object timezone-aware (set it to UTC)
                aware_utc_time = utc_tz.localize(tx['timestamp'])
                # Convert to IST
                ist_time = aware_utc_time.astimezone(ist_tz)
                tx['timestamp_ist'] = ist_time
                transactions.append(tx)

        return render_template('user_dashboard.html', account=account_details, transactions=transactions)
    except pymysql.MySQLError as e:
        flash(f'Could not load dashboard: {e}', 'error')
        return redirect(url_for('login'))
    finally:
        conn.close()


@app.route('/transfer', methods=['GET', 'POST'])
@login_required
def transfer():
    if request.method == 'POST':
        recipient_identifier = request.form['recipient_identifier']
        amount = float(request.form['amount'])
        pin = request.form['pin']

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT pin_hash FROM users WHERE user_id = %s", (session['user_id'],))
                sender_user = cursor.fetchone()
                cursor.execute("SELECT balance FROM accounts WHERE account_id = %s", (session['account_id'],))
                sender_account = cursor.fetchone()

                if not sender_user or not check_password_hash(sender_user['pin_hash'], pin):
                    flash('Invalid PIN.', 'error')
                    return redirect(url_for('transfer'))

                if float(sender_account['balance']) < amount:
                    flash('Insufficient funds.', 'error')
                    return redirect(url_for('transfer'))

                recipient_account = None
                if len(recipient_identifier) > 10 and recipient_identifier.upper().startswith('AAPNA'):
                    cursor.execute("SELECT a.account_id, a.user_id, u.first_name, u.last_name FROM accounts a JOIN users u ON a.user_id = u.user_id WHERE a.account_number = %s", (recipient_identifier,))
                else:
                    cursor.execute("""
                        SELECT a.account_id, a.user_id, u.first_name, u.last_name FROM accounts a
                        JOIN users u ON u.user_id = a.user_id
                        WHERE u.phone_number = %s
                    """, (recipient_identifier,))
                recipient_account = cursor.fetchone()

                if not recipient_account:
                    flash('Recipient not found. Please check the Account or Phone Number.', 'error')
                    return redirect(url_for('transfer'))

                if recipient_account['account_id'] == session['account_id']:
                    flash('You cannot transfer money to your own account.', 'error')
                    return redirect(url_for('transfer'))

                recipient_name = f"{recipient_account['first_name']} {recipient_account['last_name']}"
                sender_name = session.get('user_name', 'an account holder')
                
                cursor.execute("UPDATE accounts SET balance = balance - %s WHERE account_id = %s", (amount, session['account_id']))
                cursor.execute("UPDATE accounts SET balance = balance + %s WHERE account_id = %s", (amount, recipient_account['account_id']))

                cursor.execute(
                    "INSERT INTO transactions (account_id, transaction_type, amount, description) VALUES (%s, 'Debit', %s, %s)",
                    (session['account_id'], amount, f"Transfer to {recipient_name}")
                )
                
                cursor.execute(
                    "INSERT INTO transactions (account_id, transaction_type, amount, description) VALUES (%s, 'Credit', %s, %s)",
                    (recipient_account['account_id'], amount, f"Received from {sender_name}")
                )
                conn.commit()
            
            flash('Transfer successful!', 'success')
            return redirect(url_for('dashboard'))
        except pymysql.MySQLError as e:
            conn.rollback()
            flash(f'An error occurred: {e}', 'error')
            return redirect(url_for('transfer'))
        finally:
            conn.close()

    return render_template('transfer_money.html')


@app.route('/transactions')
@login_required
def transaction_history():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM transactions WHERE account_id = %s ORDER BY timestamp DESC",
                (session['account_id'],)
            )
            transactions_utc = cursor.fetchall()

            # Convert timestamps to IST
            transactions = []
            utc_tz = pytz.utc
            ist_tz = pytz.timezone('Asia/Kolkata')
            for tx in transactions_utc:
                aware_utc_time = utc_tz.localize(tx['timestamp'])
                ist_time = aware_utc_time.astimezone(ist_tz)
                tx['timestamp_ist'] = ist_time
                transactions.append(tx)

        return render_template('transaction_history.html', transactions=transactions)
    except pymysql.MySQLError as e:
        flash(f'Could not load transaction history: {e}', 'error')
        return redirect(url_for('dashboard'))
    finally:
        conn.close()

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))


# --- MANAGER ROUTES ---
@app.route('/manager/login', methods=['GET', 'POST'])
def manager_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM employees WHERE email = %s", (email,))
                manager = cursor.fetchone()
            
            if manager and check_password_hash(manager['password_hash'], password):
                session['manager_loggedin'] = True
                session['manager_id'] = manager['employee_id']
                return redirect(url_for('manager_dashboard'))
            else:
                flash('Invalid manager credentials.', 'error')
        except pymysql.MySQLError as e:
            flash(f'Database error: {e}', 'error')
        finally:
            conn.close()
            
    return render_template('manager_login.html')

@app.route('/manager/dashboard')
@manager_login_required
def manager_dashboard():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT u.user_id, u.first_name, u.last_name, u.status,
                       a.account_number, a.balance
                FROM users u JOIN accounts a ON u.user_id = a.user_id
                ORDER BY u.user_id DESC
            """)
            users = cursor.fetchall()
        return render_template('manager_dashboard.html', users=users)
    except pymysql.MySQLError as e:
        flash(f'Could not load manager dashboard: {e}', 'error')
        return redirect(url_for('manager_login'))
    finally:
        conn.close()

@app.route('/manager/create_customer', methods=['GET', 'POST'])
@manager_login_required
def create_customer():
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        email = request.form['email']
        phone_number = request.form['phone_number']
        password = request.form['password']
        pin = request.form['pin']

        if not phone_number.isdigit() or len(phone_number) != 10:
            flash('Phone number must be exactly 10 digits.', 'error')
            return redirect(url_for('create_customer'))
        
        initial_deposit = 0.0
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        hashed_pin = generate_password_hash(pin, method='pbkdf2:sha256')

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM users WHERE email = %s OR phone_number = %s", (email, phone_number))
                if cursor.fetchone():
                    flash('An account with this email or phone number already exists.', 'error')
                    return redirect(url_for('create_customer'))

                cursor.execute(
                    "INSERT INTO users (first_name, last_name, email, phone_number, password_hash, pin_hash) VALUES (%s, %s, %s, %s, %s, %s)",
                    (first_name, last_name, email, phone_number, hashed_password, hashed_pin)
                )
                user_id = cursor.lastrowid
                account_number = f"AAPNA{user_id:07d}"
                cursor.execute(
                    "INSERT INTO accounts (user_id, account_number, balance) VALUES (%s, %s, %s)",
                    (user_id, account_number, initial_deposit)
                )
                conn.commit()
                flash(f'Customer account created successfully! The new account number is {account_number}.', 'success')
                return redirect(url_for('manager_dashboard'))
        except pymysql.MySQLError as e:
            flash(f'An error occurred: {e}', 'error')
        finally:
            conn.close()
            
    return render_template('create_customer.html')


@app.route('/manager/toggle_status/<int:user_id>')
@manager_login_required
def toggle_status(user_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT status FROM users WHERE user_id = %s", (user_id,))
            current_status = cursor.fetchone()['status']
            new_status = 'Inactive' if current_status == 'Active' else 'Active'
            cursor.execute("UPDATE users SET status = %s WHERE user_id = %s", (new_status, user_id))
            conn.commit()
        flash('User status updated.', 'success')
    except pymysql.MySQLError as e:
        flash(f'Error updating status: {e}', 'error')
    finally:
        conn.close()
    return redirect(url_for('manager_dashboard'))


@app.route('/manager/transaction', methods=['GET', 'POST'])
@manager_login_required
def manager_transaction():
    account_number = request.args.get('account_number', '')
    action = request.args.get('action', 'deposit')

    if request.method == 'POST':
        account_number = request.form['account_number']
        amount = float(request.form['amount'])
        action = request.form['action']
        
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT account_id, balance FROM accounts WHERE account_number = %s", (account_number,))
                account = cursor.fetchone()
                
                if not account:
                    flash('Account not found.', 'error')
                    return redirect(url_for('manager_dashboard'))

                account_id = account['account_id']
                
                if action == 'deposit':
                    cursor.execute("UPDATE accounts SET balance = balance + %s WHERE account_id = %s", (amount, account_id))
                    description = 'Cash Deposit by Bank'
                    trans_type = 'Credit'
                elif action == 'withdraw':
                    if float(account['balance']) < amount:
                        flash('Insufficient funds for withdrawal.', 'error')
                        return redirect(url_for('manager_transaction', account_number=account_number, action='withdraw'))
                    cursor.execute("UPDATE accounts SET balance = balance - %s WHERE account_id = %s", (amount, account_id))
                    description = 'Cash Withdrawal by Bank'
                    trans_type = 'Debit'
                
                cursor.execute(
                    "INSERT INTO transactions (account_id, transaction_type, amount, description) VALUES (%s, %s, %s, %s)",
                    (account_id, trans_type, amount, description)
                )
                conn.commit()
            flash(f'{action.capitalize()} successful.', 'success')
            return redirect(url_for('manager_dashboard'))
        except pymysql.MySQLError as e:
            conn.rollback()
            flash(f'An error occurred: {e}', 'error')
        finally:
            conn.close()

    return render_template('manager_transaction.html', account_number=account_number, action=action)


@app.route('/manager/update_user/<int:user_id>', methods=['GET', 'POST'])
@manager_login_required
def update_user(user_id):
    conn = get_db_connection()
    try:
        if request.method == 'POST':
            new_first_name = request.form['first_name']
            new_last_name = request.form['last_name']
            new_email = request.form['email']
            new_phone = request.form['phone_number']

            with conn.cursor() as cursor:
                cursor.execute("SELECT user_id FROM users WHERE (email = %s OR phone_number = %s) AND user_id != %s", (new_email, new_phone, user_id))
                if cursor.fetchone():
                    flash('Email or phone number is already in use by another account.', 'error')
                    return redirect(url_for('update_user', user_id=user_id))

                cursor.execute("""
                    UPDATE users SET first_name = %s, last_name = %s, email = %s, phone_number = %s
                    WHERE user_id = %s
                """, (new_first_name, new_last_name, new_email, new_phone, user_id))
                conn.commit()

            flash('Customer details updated successfully!', 'success')
            return redirect(url_for('manager_dashboard'))
        
        else:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT u.user_id, u.first_name, u.last_name, u.email, u.phone_number, a.account_number
                    FROM users u JOIN accounts a ON u.user_id = a.user_id
                    WHERE u.user_id = %s
                """, (user_id,))
                user = cursor.fetchone()
            
            if user:
                return render_template('update_user.html', user=user)
            else:
                flash('User not found.', 'error')
                return redirect(url_for('manager_dashboard'))

    except pymysql.MySQLError as e:
        flash(f'An error occurred: {e}', 'error')
        return redirect(url_for('manager_dashboard'))
    finally:
        conn.close()


@app.route('/manager/logout')
@manager_login_required
def manager_logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('manager_login'))


# --- DB INITIALIZATION ---
def init_db():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM employees WHERE email = 'manager@bank.com'")
            if cursor.fetchone() is None:
                hashed_pass = generate_password_hash('admin123', method='pbkdf2:sha256')
                cursor.execute(
                    "INSERT INTO employees (first_name, last_name, email, password_hash) VALUES (%s, %s, %s, %s)",
                    ('Bank', 'Manager', 'manager@bank.com', hashed_pass)
                )
                conn.commit()
                print("Default manager created.")
    finally:
        conn.close()

# --- MAIN EXECUTION ---
if __name__ == '__main__':
    # init_db()
    app.run(debug=True, port=5001)

