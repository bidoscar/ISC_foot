from flask import Flask, request, render_template, g, redirect, url_for, flash
import sqlite3
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Replace with a real secret key in production

DATABASE = 'forecasts.db'

# Initialize Flask-Login and Flask-Bcrypt
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

bcrypt = Bcrypt(app)


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
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
        if user:
            return User(user[0], user[1], user[2], user[3])
        return None

    @staticmethod
    def find_by_username(username):
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT id, username, email, password FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        if user:
            return User(user[0], user[1], user[2], user[3])
        return None

    @staticmethod
    def find_by_email(email):
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT id, username, email, password FROM users WHERE email = ?', (email,))
        user = cursor.fetchone()
        if user:
            return User(user[0], user[1], user[2], user[3])
        return None


@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        db = get_db()
        cursor = db.cursor()
        try:
            cursor.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)', (username, email, hashed_password))
            db.commit()
            flash('Registration successful. Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError as e:
            if 'username' in str(e):
                flash('Username already exists. Please choose a different one.', 'danger')
            elif 'email' in str(e):
                flash('Email already exists. Please choose a different one.', 'danger')
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.find_by_username(username)
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            flash('Login successful!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Login failed. Please check your username and password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

@app.route('/submit', methods=['POST'])
@login_required
def submit():
    first_place = request.form['firstPlace']
    second_place = request.form['secondPlace']
    third_place = request.form['thirdPlace']
    percentage = request.form['percentage']

    db = get_db()
    cursor = db.cursor()
    cursor.execute('''
        INSERT INTO forecasts (user_id, first_place, second_place, third_place, percentage)
        VALUES (?, ?, ?, ?, ?)
    ''', (current_user.id, first_place, second_place, third_place, percentage))
    db.commit()

    return 'Forecast submitted! Thank you and Bye Bye.'

@app.route('/forecasts')
@login_required
def forecasts():
    db = get_db()
    cursor = db.cursor()
    cursor.execute('''
        SELECT 
            forecasts.first_place, 
            forecasts.second_place, 
            forecasts.third_place, 
            forecasts.percentage, 
            users.username, 
            users.email, 
            users.password 
        FROM forecasts
        JOIN users ON forecasts.user_id = users.id
        WHERE forecasts.user_id = ?
    ''', (current_user.id,))
    forecasts = cursor.fetchall()
    return render_template('forecasts.html', forecasts=forecasts)


import csv
from io import StringIO
from flask import make_response

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


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
