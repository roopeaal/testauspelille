from flask import Flask, render_template, request, redirect, url_for, flash, make_response
from geopy.distance import geodesic
import random
import mysql.connector

app = Flask(__name__)

# Tietokantayhteyden avausfunktio
def get_db_connection():
    conn = mysql.connector.connect(
        host='127.0.0.1',
        port=3306,
        database='lentopeli',
        user='root',
        password='juhannus',
        autocommit=True
    )
    return conn

# Tietokantayhteyden avaaminen ja sulkeminen tietokantakäsittelyissä
def execute_query(query, values=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if values:
            cursor.execute(query, values)
        else:
            cursor.execute(query)
        result = cursor.fetchall()
        conn.commit()
        return result
    except Exception as e:
        flash(str(e), 'danger')
        return None
    finally:
        cursor.close()
        conn.close()

@app.route('/')
def index():
    username = request.cookies.get('username')
    return render_template('index.html', username=username)

@app.route('/register', methods=['GET', 'POST'])
def register():
    try:
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, password FROM game WHERE username=%s", (username,))
            existing_user = cursor.fetchone()

            if existing_user:
                flash('Username already taken. Please choose another one.', 'danger')
            else:
                cursor.execute("INSERT INTO game (username, password) VALUES (%s, %s)", (username, password))
                conn.commit()
                flash('Registration successful. You can now log in.', 'success')
                return redirect(url_for('login'))

            cursor.close()
            conn.close()

    except Exception as e:
        flash(str(e), 'danger')

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if check_login(username, password):
            response = make_response(redirect(url_for('game')))
            response.set_cookie('username', username)
            return response
        else:
            flash("Invalid username or password", 'danger')

    return render_template('login.html')

def check_login(username, password):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, password FROM game WHERE username=%s", (username,))
    user_data = cursor.fetchone()
    conn.close()

    # Tarkista onko user_data olemassa ja onko salasana oikea
    if user_data and user_data['password'] == password:
        return True
    else:
        return False

@app.route('/logout')
def logout():
    response = make_response(redirect(url_for('index')))
    response.delete_cookie('username')
    return response

# Tässä osioissa on sinun pelilogiikkasi, jota on sovellettu Flask-sovellukseen.
# Arvo uusi maa ja kenttä
def arvo_uusi_maa_ja_kentta():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT country.name, MAX(airport.name) AS largest_airport, country.latitude, country.longitude 
        FROM country 
        INNER JOIN airport ON country.iso_country = airport.iso_country 
        WHERE airport.type = 'large_airport' 
        GROUP BY country.name, country.latitude, country.longitude;
    """)
    tiedot = cursor.fetchall()
    arvottu_tieto = random.choice(tiedot)
    cursor.close()
    conn.close()
    return arvottu_tieto

# Laske etäisyys
def laske_etaisyys(koordinaatit1, koordinaatit2):
    return geodesic(koordinaatit1, koordinaatit2).kilometers

# Lisää pisteet
def lisaa_pisteet(username):
    arvottu_latitude, arvottu_longitude = arvo_uusi_maa_ja_kentta()
    pelaajan_latitude = 64
    pelaajan_longitude = 26
    etaisyys = laske_etaisyys((pelaajan_latitude, pelaajan_longitude), (arvottu_latitude, arvottu_longitude))
    pisteet = max(100 - app.config['pisteet'], 0)
    if etaisyys <= 500:
        pisteet += 100
    elif etaisyys <= 1000:
        pisteet += 50
    elif etaisyys <= 1500:
        pisteet += 20
    else:
        pisteet += 10

    # Tallenna pisteet tietokantaan
    execute_query("INSERT INTO scores (username, points) VALUES (%s, %s)", (username, pisteet))

@app.route('/game')
def game():
    username = request.cookies.get('username')
    if username:
        arvottu_maa, arvottu_kentta, arvottu_latitude, arvottu_longitude = arvo_uusi_maa_ja_kentta()
        etaisyys = laske_etaisyys((64, 26), (arvottu_latitude, arvottu_longitude))
        return render_template('game.html', country=arvottu_maa, airport=arvottu_kentta, distance=etaisyys)
    else:
        flash('You need to log in to play the game.', 'info')
        return redirect(url_for('login'))

@app.route('/highscores')
def highscores():
    highscore_list = execute_query("SELECT username, MAX(points) as points FROM scores GROUP BY username ORDER BY points DESC LIMIT 10")
    return render_template('highscores.html', highscores=highscore_list)

if __name__ == '__main__':
    app.secret_key = 'supersecretkey'
    app.config['pisteet'] = 0
    app.run(debug=True)
