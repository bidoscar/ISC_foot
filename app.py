from flask import Flask, render_template, request, redirect, url_for, session, make_response, g
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
import sqlite3
import csv
from io import StringIO
import time

app = Flask(__name__)
app.secret_key = 'your_secret_key'
DATABASE = 'site.db'

# Initialize Flask-Login and Flask-Bcrypt
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

bcrypt = Bcrypt(app)

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row  # This helps to fetch rows as dictionaries
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS forecasts (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                first_place TEXT,
                second_place TEXT,
                third_place TEXT,
                percentage INTEGER,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        db.commit()

class User(UserMixin):
    def __init__(self, id, username, email, password):
        self.id = id
        self.username = username
        self.email = email
        self.password = password

    @staticmethod
    def get(user_id):
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT id, username, email, password FROM users WHERE id = ?', (user_id,))
        user = cursor.fetchone()
        if not user:
            return None
        return User(user[0], user[1], user[2], user[3])

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

@app.route('/')
def home():
    if 'username' in session:
        return redirect(url_for('submit_forecast'))
    return redirect(url_for('register'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])

        db = get_db()
        cursor = db.cursor()

        for _ in range(5):  # Retry up to 5 times
            try:
                cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
                existing_user = cursor.fetchone()
                if existing_user:
                    return 'Username already exists!'

                cursor.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)', (username, email, password))
                db.commit()
                return redirect(url_for('login'))
            except sqlite3.OperationalError as e:
                if 'database is locked' in str(e):
                    time.sleep(0.1)  # Wait for 100 milliseconds before retrying
                else:
                    raise

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT id, password FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        if user and check_password_hash(user[1], password):
            session['username'] = username
            login_user(User(user[0], username, None, user[1]))
            return redirect(url_for('submit_forecast'))
        error = 'Invalid username or password!'

    return render_template('login.html', error=error)

@app.route('/submit', methods=['GET', 'POST'])
@login_required
def submit_forecast():
    success = False
    if request.method == 'POST':
        first_place = request.form['firstPlace']
        second_place = request.form['secondPlace']
        third_place = request.form['thirdPlace']
        percentage = request.form['percentage']

        # Debug print statements
        print(f"Received forecast: {first_place}, {second_place}, {third_place}, {percentage}")

        db = get_db()
        cursor = db.cursor()

        for _ in range(5):  # Retry up to 5 times
            try:
                cursor.execute('''
                    INSERT INTO forecasts (user_id, first_place, second_place, third_place, percentage)
                    VALUES (?, ?, ?, ?, ?)
                ''', (current_user.id, first_place, second_place, third_place, percentage))
                db.commit()
                print("Forecast successfully saved to the database")
                success = True  # Set success flag
                break
            except sqlite3.OperationalError as e:
                if 'database is locked' in str(e):
                    print("Database is locked, retrying...")
                    time.sleep(0.1)  # Wait for 100 milliseconds before retrying
                else:
                    raise

    return render_template('index.html', success=success)


@app.route('/forecasts')
@login_required
def forecasts_page():
    db = get_db()
    cursor = db.cursor()
    cursor.execute('''
        SELECT 
            forecasts.first_place, 
            forecasts.second_place, 
            forecasts.third_place, 
            forecasts.percentage, 
            users.username, 
            users.email 
        FROM forecasts
        JOIN users ON forecasts.user_id = users.id
        WHERE forecasts.user_id = ?
    ''', (current_user.id,))
    rows = cursor.fetchall()
    
    forecasts = []
    for row in rows:
        forecast = {
            'first_place': row['first_place'],
            'second_place': row['second_place'],
            'third_place': row['third_place'],
            'percentage': row['percentage'],
            'username': row['username'],
            'email': row['email']
        }
        forecasts.append(forecast)
    
    return render_template('forecasts.html', forecasts=forecasts)

@app.route('/logout')
def logout():
    session.pop('username', None)
    logout_user()
    return redirect(url_for('login'))

@app.route('/download_csv')
@login_required
def download_csv():
    db = get_db()
    cursor = db.cursor()
    cursor.execute('''
        SELECT 
            forecasts.first_place, 
            forecasts.second_place, 
            forecasts.third_place, 
            forecasts.percentage, 
            users.username, 
            users.email 
        FROM forecasts
        JOIN users ON forecasts.user_id = users.id
        WHERE forecasts.user_id = ?
    ''', (current_user.id,))
    data = cursor.fetchall()

    # Create a CSV file in memory
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['First Place', 'Second Place', 'Third Place', 'Percentage', 'Username', 'Email'])
    cw.writerows(data)
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=forecasts.csv"
    output.headers["Content-type"] = "text/csv"
    return output

@app.route('/check_forecasts')
def check_forecasts():
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM forecasts')
    forecasts = cursor.fetchall()
    for forecast in forecasts:
        print(forecast)
    return 'Check console for forecasts data'

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
