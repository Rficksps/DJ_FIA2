# API KEY 0f073552908a9ed6a20e3d376bdab88f

import os
import requests
import datetime
import sqlite3
import time
from flask import Flask, render_template, request, redirect, url_for, flash, session
from markupsafe import Markup
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 's3cr3t'

UPLOAD_FOLDER = 'static/images'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def init_db():
    with app.app_context():
        db = sqlite3.connect('events2.db')  # Use 'events2.db' for events
        cursor = db.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT UNIQUE, password TEXT)''')
        db.commit()

        # Check if the "image_path" column exists, and if not, add it
        cursor.execute('''PRAGMA table_info(events)''')
        columns = [column[1] for column in cursor.fetchall()]
        if 'image_path' not in columns:
            cursor.execute('''ALTER TABLE events ADD COLUMN image_path TEXT''')
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
            with sqlite3.connect('users.db') as db:
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
        with sqlite3.connect('users.db') as db:
            cursor = db.cursor()
            cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
            user = cursor.fetchone()
            if user and check_password_hash(user[1], password):
                session['user'] = user[0]
                return redirect(url_for('home'))
            else:
                flash('Invalid username or password!', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('home'))

@app.route('/join_event')
def join_event():
    conn = sqlite3.connect('events2.db')
    cursor = conn.cursor()
    select_query = 'SELECT * FROM events'
    cursor.execute(select_query)
    events = cursor.fetchall()

    times = {}
    for event in events:
        times[event[0]] = datetime.datetime.fromtimestamp(int(event[2]))

    conn.close()

    return render_template('join_event.html', events=events, times=times)

@app.route('/event_details/<event_id>')
def event_details(event_id):
    conn = sqlite3.connect('events2.db')
    cursor = conn.cursor()
    select_query = 'SELECT * FROM events WHERE name = ?'
    cursor.execute(select_query, (event_id,))
    event = cursor.fetchone()
    conn.close()

    if event:
        event_time = datetime.datetime.fromtimestamp(int(event[2])).strftime('%H:%M:%S-%d-%m-%Y')
        event_image_path = event[3] if event[3] else 'default_event_image.jpg'
        return render_template('event_details.html', event=event, event_time=event_time, event_image_path=event_image_path)
    else:
        flash('Event not found!', 'danger')
        return redirect(url_for('join_event'))

@app.route('/create_event', methods=['GET', 'POST'])
def create_event():
    if request.method == 'POST':
        name = request.form['event_name']
        description = request.form['event_description']
        event_time = request.form['event_time']

        event_time_obj = datetime.datetime.strptime(event_time, '%Y-%m-%dT%H:%M')
        event_time_unix = int(event_time_obj.timestamp())

        event_image = request.files['event_image']
        if event_image:
            # Save the image to a specific folder
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(event_image.filename))
            event_image.save(image_path)
        else:
            # Use a default image path if no image is provided
            image_path = 'default_image_path.jpg'

        conn = sqlite3.connect('events2.db')
        cursor = conn.cursor()

        insert_query = 'INSERT INTO events (name, description, time, image_path) VALUES (?, ?, ?, ?)'
        cursor.execute(insert_query, (name, description, event_time_unix, image_path))

        conn.commit()
        conn.close()

        return redirect(url_for('home'))

    return render_template('create_event.html')


def unixtimestampformat(value):
    formatted_date = time.strftime('%H:%M/%d/%m/%Y', time.localtime(value))
    return Markup(formatted_date)

app.jinja_env.filters['unixtimestampformat'] = unixtimestampformat

@app.route('/account')
def account():
    return render_template('account.html')

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

