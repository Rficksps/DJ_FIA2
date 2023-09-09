# API KEY 0f073552908a9ed6a20e3d376bdab88f

import os
import requests
import datetime
import sqlite3
import time
from datetime import timezone
import secrets
import string
from flask import Flask, render_template, request, redirect, url_for, flash, session
from markupsafe import Markup
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app = Flask(__name__)
app.secret_key = 's3cr3t'

UPLOAD_FOLDER = 'static/images'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def init_db():
    with app.app_context():
        db = sqlite3.connect('events3.db')  # Use 'events3.db' for events
        cursor = db.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, description TEXT, time INTEGER, image_path TEXT, event_code TEXT)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS playlist (id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER, user_id INTEGER, FOREIGN KEY (event_id) REFERENCES events(id), FOREIGN KEY (user_id) REFERENCES users(id))''')

        db.commit()

        # Check if the "image_path" column exists, and if not, add it
        cursor.execute('''PRAGMA table_info(events)''')
        columns = [column[1] for column in cursor.fetchall()]
        if 'image_path' not in columns:
            cursor.execute('''ALTER TABLE events ADD COLUMN image_path TEXT''')
            db.commit()

        # Check if the "event_code" column exists, and if not, add it
        if 'event_code' not in columns:
            cursor.execute('''ALTER TABLE events ADD COLUMN event_code TEXT''')
            db.commit()





@app.route('/')
def home():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = generate_password_hash(password, method='sha256')
        try:
            with sqlite3.connect('events3.db') as db:
                cursor = db.cursor()
                cursor.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed_password))
                db.commit()
            flash('Registered successfully!', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username already exists!', 'danger')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        with sqlite3.connect('events3.db') as db:
            cursor = db.cursor()
            cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
            user = cursor.fetchone()
            if user and check_password_hash(user[2], password):
                session['user'] = user[1]
                return redirect(url_for('home'))
            else:
                flash('Invalid username or password!', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('home'))


@app.route('/events', methods=['GET', 'POST'])
def join_event():
    if request.method == 'POST':
        event_code = request.form['event_code']

        # Check if the event code is alphanumeric (letters and digits only)
        if not event_code.isalnum():
            flash('Invalid event code format!', 'danger')
            return redirect(url_for('join_event'))

        # Check if the event code exists in the database
        conn = sqlite3.connect('events3.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM events WHERE event_code = ?', (event_code,))
        event_id = cursor.fetchone()
        conn.close()

        if event_id:
            # If the event code exists, add an entry to the playlist table
            conn = sqlite3.connect('events3.db')
            cursor = conn.cursor()

            # Get the user's ID from the session
            cursor.execute('SELECT id FROM users WHERE username = ?', (session['user'],))
            user_id = cursor.fetchone()

            # Insert the user's ID and event ID into the playlist table
            cursor.execute('INSERT INTO playlist (user, event) VALUES (?, ?)', (user_id[0], event_id[0]))
            conn.commit()
            conn.close()
            flash('Joined the event successfully!', 'success')
        else:
            flash('Event code not found!', 'danger')

        return redirect(url_for('join_event'))

    # Fetch events from the database based on user join status
    conn = sqlite3.connect('events3.db')
    cursor = conn.cursor()

    # Get the user's ID from the session
    cursor.execute('SELECT id FROM users WHERE username = ?', (session['user'],))
    user_id = cursor.fetchone()

    if user_id:
        # Fetch events that the user has joined
        cursor.execute(
            'SELECT events.id, events.name, events.description, events.time FROM events JOIN playlist ON events.id = playlist.event WHERE playlist.user = ?',
            (user_id[0],))
        joined_events = cursor.fetchall()

        # Fetch events that the user has not joined
        cursor.execute(
            'SELECT id, name, description, time FROM events WHERE id NOT IN (SELECT event FROM playlist WHERE user = ?)',
            (user_id[0],))
        other_events = cursor.fetchall()
    else:
        # If the user is not logged in, display all events
        cursor.execute('SELECT * FROM events')
        events = cursor.fetchall()

    conn.close()

    return render_template('join_event.html', joined_events=joined_events, other_events=other_events)


@app.route('/event_details/<event_id>')
def event_details(event_id):
    try:
        conn = sqlite3.connect('events3.db')
        cursor = conn.cursor()

        # Check if the event ID exists in the database
        cursor.execute('SELECT * FROM events WHERE id = ?', (event_id,))
        event = cursor.fetchone()

        if event:
            # Fetch the list of users who have joined the event
            cursor.execute('SELECT username FROM users INNER JOIN playlist ON users.id = playlist.user WHERE playlist.event = ?', (event_id,))
            event_users = [row[0] for row in cursor.fetchall()]

            return render_template('event_details.html', event=event, event_users=event_users)
        else:
            flash('Event not found!', 'danger')
            return redirect(url_for('join_event'))

    except ValueError:
        flash('Invalid event ID!', 'danger')
        return redirect(url_for('join_event'))





from datetime import datetime

@app.route('/create_event', methods=['GET', 'POST'])
def create_event():
    if request.method == 'POST':
        name = request.form['event_name']
        description = request.form['event_description']
        event_time_str = request.form['event_time']  # Get the datetime string from the form

        try:
            # Parse the event_time_str into a datetime object
            event_time_obj = datetime.strptime(event_time_str, '%Y-%m-%dT%H:%M')

            # Convert the event_time to a Unix timestamp (in UTC)
            event_time_unix = event_time_obj.replace(tzinfo=timezone.utc).timestamp()

            event_image = request.files['event_image']
            if event_image:
                # Save the image to a specific folder
                image_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(event_image.filename))
                event_image.save(image_path)
            else:
                # Use a default image path if no image is provided
                image_path = 'default_image_path.jpg'

            event_code = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(8))

            conn = sqlite3.connect('events3.db')
            cursor = conn.cursor()

            insert_query = 'INSERT INTO events (name, description, time, image_path, event_code) VALUES (?, ?, ?, ?, ?)'
            cursor.execute(insert_query, (name, description, event_time_unix, image_path, event_code))

            conn.commit()
            conn.close()

            return redirect(url_for('home'))

        except ValueError:
            flash('Invalid event time format!', 'danger')

    return render_template('create_event.html')




def unixtimestampformat(value):
    formatted_date = time.strftime('%H:%M/%d/%m/%Y', time.localtime(value))
    return Markup(formatted_date)

app.jinja_env.filters['unixtimestampformat'] = unixtimestampformat

@app.route('/account')
def account():
    if 'user' in session:
        user_id = None
        username = session['user']
        with sqlite3.connect('events3.db') as db:
            cursor = db.cursor()
            cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
            user = cursor.fetchone()
            if user:
                user_id = user[0]
        return render_template('account.html', current_user={'username': username, 'id': user_id})
    else:
        flash('You must be logged in to access your account.', 'danger')
        return redirect(url_for('login'))


@app.route('/search_song', methods=['GET', 'POST'])
def search_song():
    if request.method == 'POST':
        track_name = request.form.get('track_name', '')
        api_key = '0f073552908a9ed6a20e3d376bdab88f'
        url = f'http://ws.audioscrobbler.com/2.0/?method=track.search&track={track_name}&api_key={api_key}&format=json'

        response = requests.get(url)
        data = response.json()

        track_matches = []
        if 'results' in data and 'trackmatches' in data['results']:
            for track_info in data['results']['trackmatches']['track']:
                track_name = track_info['name']
                artist = track_info['artist']
                print(track_info)
                album_name, album_image = get_album_info(track_name, artist, api_key)
                track_info['album_name'] = album_name
                track_info['album_image'] = album_image
                track_matches.append(track_info)

        return render_template('search_results.html', track_matches=track_matches)

    return render_template('search_song.html')

def get_album_info(track_name, artist, api_key):
    url = f'http://ws.audioscrobbler.com/2.0/?method=track.getInfo&artist={artist}&track={track_name}&api_key={api_key}&format=json'

    response = requests.get(url)
    data = response.json()

    album_name = ""
    album_image = ""

    if 'track' in data and 'album' in data['track']:
        album_name = data['track']['album']['title']
        if 'image' in data['track']['album'] and data['track']['album']['image']:
            album_image = data['track']['album']['image'][-1]['#text']

    return album_name, album_image

if __name__ == '__main__':
    init_db()
    app.run(debug=True)