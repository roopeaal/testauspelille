from flask import Flask, render_template, request, redirect, url_for, flash, make_response, jsonify
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

# Arvotaan uusi maa ja kenttä ja tallennetaan koordinaatit evästeisiin
def arvo_uusi_maa_ja_kentta():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Haetaan satunnainen maa ja sen suurin lentokenttä
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
    except Exception as e:
        print("Virhe uutta maata ja kenttää arvottaessa:", e)
        return None

@app.route('/get_largest_airport_name')
def get_largest_airport_name():
    arvottu_tieto = arvo_uusi_maa_ja_kentta()
    largest_airport_name = arvottu_tieto[1]
    return jsonify({'largest_airport_name': largest_airport_name})


def laske_etaisyys_ja_ilmansuunta(koordinaatit1, koordinaatit2):
    if None in koordinaatit1 or None in koordinaatit2:
        return None, None  # Palauta None, jos jompikumpi koordinaatti on None

    # Laske etäisyys ja pyöristä se kokonaisluvuksi
    etaisyys = round(geodesic(koordinaatit1, koordinaatit2).kilometers)

    # Laske ilmansuunta
    suunta = math.degrees(
        math.atan2(koordinaatit2[1] - koordinaatit1[1], koordinaatit2[0] - koordinaatit1[0]))
    if suunta < 0:
        suunta += 360  # Muuta negatiiviset suunnat positiivisiksi

    ilmansuunta = None
    if 24 <= suunta < 69:
        ilmansuunta = "koillisessa"
    elif 69 <= suunta < 114:
        ilmansuunta = "idässä"
    elif 114 <= suunta < 159:
        ilmansuunta = "kaakossa"
    elif 159 <= suunta < 204:
        ilmansuunta = "etelässä"
    elif 204 <= suunta < 249:
        ilmansuunta = "lounaassa"
    elif 249 <= suunta < 294:
        ilmansuunta = "lännessä"
    elif 294 <= suunta < 337:
        ilmansuunta = "luoteessa"
    elif 337 <= suunta < 360 or 0 <= suunta < 24:
        ilmansuunta = "pohjoisessa"

    return etaisyys, ilmansuunta

def lisaa_pisteet(username, points):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE game SET hiscore = %s WHERE username = %s AND %s > hiscore", (points, username, points))
        conn.commit()
    except Exception as e:
        print("Virhe päivittäessä pistetilannetta:", e)
    finally:
        cursor.close()
        conn.close()

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

@app.route('/game', methods=['GET', 'POST'])
def game():
    username = request.cookies.get('username')

    # Tarkistetaan, onko arvottu maa ja koordinaatit jo tallennettu evästeisiin
    arvottu_maa = request.cookies.get('arvottu_maa')
    arvottu_latitude = request.cookies.get('arvottu_latitude')
    arvottu_longitude = request.cookies.get('arvottu_longitude')

    # Pisteiden alustaminen
    if 'points' not in request.cookies:
        points = 2100
    else:
        points = int(request.cookies.get('points'))

    # Jos koordinaatit puuttuvat, arvotaan uudet maat ja koordinaatit
    if arvottu_maa is None or arvottu_latitude is None or arvottu_longitude is None:
        arvottu_tieto = arvo_uusi_maa_ja_kentta()
        arvottu_maa = arvottu_tieto[0]
        arvottu_latitude = str(arvottu_tieto[2])
        arvottu_longitude = str(arvottu_tieto[3])

        # Tallennetaan uudet koordinaatit evästeisiin
        response = make_response(render_template('game.html', points=points))
        response.set_cookie('arvottu_maa', arvottu_maa)
        response.set_cookie('arvottu_latitude', arvottu_latitude)
        response.set_cookie('arvottu_longitude', arvottu_longitude)
        return response

    tulos = None
    result_category = None
    etaisyys = None
    ilmansuunta = None

    if request.method == 'POST':
        pelaajan_maa = request.form.get('pelaajan_maa')
        if pelaajan_maa:
            if tarkista_maa_tietokannasta(pelaajan_maa):
                pelaajan_maa_koord = hae_maan_koordinaatit(pelaajan_maa)
                pelaajan_maa_koord = tuple(map(float, pelaajan_maa_koord))  # Muuta merkkijonoista liukuluvuiksi
                arvottu_latitude = float(arvottu_latitude)  # Muuta merkkijono liukuluvaksi
                arvottu_longitude = float(arvottu_longitude)  # Muuta merkkijono liukuluvaksi
                etaisyys, ilmansuunta = laske_etaisyys_ja_ilmansuunta(pelaajan_maa_koord,
                                                                      (arvottu_latitude, arvottu_longitude))
                if pelaajan_maa.lower() == arvottu_maa.lower():
                    tulos = (f"Arvasit oikein! Oikea maa on: {arvottu_maa}. Keräsit {points} pistettä!")
                    lisaa_pisteet(username, points)  # Päivitä pisteet tietokantaan
                else:
                    # Vähennä 100 pistettä väärästä arvauksesta
                    points -= 100
                    result_category = 'info'
                    tulos = f'Arvauksesi "{pelaajan_maa}" on väärin. Oikea maa on {etaisyys} km päässä {ilmansuunta}.'
                # Tallenna pisteet evästeisiin
                response = make_response(render_template('game.html', result=tulos, result_category=result_category, points=points))
                response.set_cookie('points', str(points))  # Update points in cookies
                return response
            else:
                tulos = "Maa on kirjoitettu väärin tai sitä ei ole olemassa."
                result_category = 'danger'
        else:
            tulos = "Syötä arvaus."

    # Tallenna pisteet evästeisiin
    response = make_response(render_template('game.html', result=tulos, result_category=result_category, points=points))
    response.set_cookie('points', str(points))
    return response

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
    app.run(debug=True)
