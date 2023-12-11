from flask import Flask, render_template, request, redirect, url_for, session, flash, make_response
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
    response.set_cookie('username', '', expires=0)
    return response



def arvo_uusi_maa_ja_kentta():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT country.name, MAX(airport.name) AS largest_airport, country.latitude, country.longitude FROM country INNER JOIN airport ON country.iso_country = airport.iso_country WHERE airport.type = 'large_airport' AND country.name LIKE 'Turks%' GROUP BY country.name, country.latitude, country.longitude;")
    tiedot = cursor.fetchall()
    arvottu_tieto = random.choice(tiedot)
    app.config['arvottu_maa'] = arvottu_tieto[0]
    app.config['arvottu_kentta'] = arvottu_tieto[1]
    cursor.close()
    conn.close()
    return arvottu_tieto[2], arvottu_tieto[3]

def laske_etaisyys(koordinaatit1, koordinaatit2):
    return geodesic(koordinaatit1, koordinaatit2).kilometers

def lisaa_pisteet(username):
    arvottu_latitude, arvottu_longitude = arvo_uusi_maa_ja_kentta()
    pelaajan_latitude = 64  # Pelaajan oletuskoordinaatit
    pelaajan_longitude = 26
    etaisyys = laske_etaisyys((pelaajan_latitude, pelaajan_longitude), (arvottu_latitude, arvottu_longitude))
    pisteet = max(100 - app.config.get('arvaukset', 0) * 10, 0)  # Lisää oletusarvo arvauksille
    app.config['loppupisteet'] += pisteet
    tallenna_pisteet(pisteet, username)

def tallenna_arvaus():
    cursor.execute("""
        INSERT INTO arvaukset (username, arvottu_maa, arvottu_kentta, pelaajan_maa)
        VALUES (%s, %s, %s, %s)
    """, (kayttaja, app.config['arvottu_maa'], app.config['arvottu_kentta'], app.config['pelaajan_maa']))

def tallenna_pisteet(pisteet, username):
    conn = get_db_connection()
    cursor = conn.cursor()
    if username:
        cursor.execute("""
            UPDATE game SET hiscore = GREATEST(hiscore, %s)
            WHERE username = %s
        """, (pisteet, username))
        conn.commit()
    cursor.close()
    conn.close()



@app.after_request
def clear_flash_cookies(response):
    response.set_cookie('flash_message', '', expires=0)
    response.set_cookie('flash_category', '', expires=0)
    return response


@app.route('/game', methods=['GET', 'POST'])
def game():
    username = request.cookies.get('username')
    if not username:
        flash("You need to log in to play the game.", "warning")
        return redirect(url_for('login'))

    if request.method == 'POST':
        pelaajan_maa = request.form.get('pelaajan_maa').strip()
        arvottu_maa, arvottu_kentta, _, _ = arvo_uusi_maa_ja_kentta()
        tarkista_arvaus(pelaajan_maa, arvottu_maa, username)

    return render_template('game.html', username=username)

def tarkista_arvaus(pelaajan_maa, arvottu_maa, username):
    if pelaajan_maa.lower() == arvottu_maa.lower():
        flash("Onnea, arvasit oikean maan!", "success")
        lisaa_pisteet(username)
    else:
        flash("Väärä arvaus, yritä uudelleen.", "danger")

def custom_flash(message, category='message'):
    response = make_response(redirect(request.url))
    response.set_cookie('flash_message', message)
    response.set_cookie('flash_category', category)
    return response


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


# Näytetään käyttäjän pisteet leaderboardissa
@app.route('/leaderboard')
def leaderboard():
    username = request.cookies.get('username')
    if not username:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Hae käyttäjän nykyinen hiscore
    cursor.execute("SELECT IFNULL(hiscore, 0) as hiscore FROM game WHERE username=%s", (username,))
    hiscore = cursor.fetchone()

    # Hae tulostaulun tiedot tietokannasta
    cursor.execute("SELECT username, IFNULL(hiscore, 0) as hiscore FROM game ORDER BY hiscore DESC LIMIT 10")
    tulostaulu = cursor.fetchall()

    return render_template('leaderboard.html', tulostaulu=tulostaulu, hiscore=hiscore['hiscore'] if hiscore else 0)


# Päivitä pisteet tietokantaan pelin lopussa
def paivita_pisteet(pisteet, username):
    if username:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE game SET hiscore = GREATEST(hiscore, %s) WHERE username = %s", (pisteet, username))
        conn.commit()
        cursor.close()
        conn.close()

if __name__ == '__main__':
    app.run(debug=True)
