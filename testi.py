from flask import Flask, render_template, request, redirect, url_for, flash, make_response
from geopy.distance import geodesic
import math
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

def laske_etaisyys_ja_ilmansuunta(koordinaatit1, koordinaatit2):
    # Laske etäisyys ja pyöristä se kokonaisluvuksi
    etaisyys = round(geodesic(koordinaatit1, koordinaatit2).kilometers)

    # Laske ilmansuunta
    lat1, lon1 = map(math.radians, koordinaatit1)
    lat2, lon2 = map(math.radians, koordinaatit2)

    dlon = lon2 - lon1
    y = math.sin(dlon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    ilmansuunta_rad = math.atan2(y, x)
    ilmansuunta_deg = math.degrees(ilmansuunta_rad)

    # Muunna asteet ilmansuunnaksi
    compass_brackets = ["Pohjoisessa", "Koillisessa", "Idässä", "Kaakossa", "Etelässä", "Lounaassa", "Lännessä", "Luoteessa", "Pohjoisessa"]
    compass_index = int(round(ilmansuunta_deg / 45))
    ilmansuunta = compass_brackets[compass_index]

    return etaisyys, ilmansuunta


@app.route('/game', methods=['GET', 'POST'])
def game():
    username = request.cookies.get('username')
    arvottu_maa = request.cookies.get('arvottu_maa')
    arvottu_latitude = request.cookies.get('arvottu_latitude')
    arvottu_longitude = request.cookies.get('arvottu_longitude')

    tulos = None
    result_category = None
    etaisyys = None
    ilmansuunta = None

    if request.method == 'POST':
        pelaajan_maa = request.form.get('pelaajan_maa')
        if pelaajan_maa:
            if tarkista_maa_tietokannasta(pelaajan_maa):
                pelaajan_maa_koord = hae_maan_koordinaatit(pelaajan_maa)
                etaisyys, ilmansuunta = laske_etaisyys_ja_ilmansuunta(pelaajan_maa_koord, (
                float(arvottu_latitude), float(arvottu_longitude)))
                if pelaajan_maa.lower() == arvottu_maa.lower():
                    tulos = "Correct! The correct country is: " + arvottu_maa
                    response = make_response(render_template('game.html', result=tulos, country=arvottu_maa))
                    response.delete_cookie('arvottu_maa')
                    response.delete_cookie('arvottu_latitude')
                    response.delete_cookie('arvottu_longitude')
                    lisaa_pisteet(username)
                    return response
                else:
                    tulos = f"Oikea maa on {etaisyys} km päässä {ilmansuunta}"
                    result_category = 'info'
            else:
                tulos = "Arvaus on kirjoitettu väärin tai sitä ei ole olemassa"
                result_category = 'danger'
        else:
            tulos = "Please enter a guess."

    return render_template('game.html', result=tulos, result_category=result_category, distance=etaisyys, direction=ilmansuunta)

def lisaa_pisteet(username):
    # Oletetaan, että arvo_uusi_maa_ja_kentta palauttaa neljä arvoa: maa, kenttä, latitude, longitude
    _, _, arvottu_latitude, arvottu_longitude = arvo_uusi_maa_ja_kentta()
    pelaajan_latitude = 64
    pelaajan_longitude = 26
    etaisyys = laske_etaisyys((pelaajan_latitude, pelaajan_longitude), (arvottu_latitude, arvottu_longitude))

    # Määritä pisteet etäisyyden perusteella
    if etaisyys <= 500:
        pisteet = 100
    elif etaisyys <= 1000:
        pisteet = 50
    elif etaisyys <= 1500:
        pisteet = 20
    else:
        pisteet = 10

    # Tallenna pisteet tietokantaan
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE game SET hiscore = hiscore + %s WHERE username = %s", (pisteet, username))
        conn.commit()
    except Exception as e:
        print("Virhe päivittäessä pistetilannetta:", e)
    finally:
        cursor.close()
        conn.close()


def laske_etaisyys(koordinaatit1, koordinaatit2):
    return geodesic(koordinaatit1, koordinaatit2).kilometers

def tarkista_maa_tietokannasta(maa):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name, latitude, longitude FROM country WHERE name = %s", (maa,))
    tulos = cursor.fetchone()
    cursor.close()
    conn.close()
    return bool(tulos)

def hae_maan_koordinaatit(maa):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT latitude, longitude FROM country WHERE name = %s", (maa,))
        koordinaatit = cursor.fetchone()
        return koordinaatit
    finally:
        cursor.close()
        conn.close()


@app.route('/leaderboard')
def leaderboard():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username, IFNULL(hiscore, 0) as hiscore FROM game ORDER BY hiscore DESC LIMIT 10;")
    top_10_scores = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('leaderboard.html', top_10_scores=top_10_scores)


@app.route('/highscores')
def highscores():
    highscore_list = execute_query("SELECT username, IFNULL(hiscore, 0) as hiscore FROM game ORDER BY hiscore DESC LIMIT 10;")
    return render_template('highscores.html', highscores=highscore_list)

if __name__ == '__main__':
    app.secret_key = 'supersecretkey'
    app.config['pisteet'] = 0
    app.run(debug=True)
