from flask import Flask, render_template, request, redirect, url_for, flash, make_response, jsonify
from geopy.distance import geodesic
import math
import random
import mysql.connector

app = Flask(__name__)


# luo seuraavat tarvittavat sql taulut:

# ALTER TABLE game ADD COLUMN points INT DEFAULT 0;
# ALTER TABLE game ADD COLUMN kierroksen_Maa VARCHAR(255);


# nollaa leaderboardi:

# UPDATE game SET hiscore = 0;


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

            # Lisää tässä vaiheessa pisteiden päivitys
            lisaa_pisteet(username, 1000)

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

    # Nollaa käyttäjän pistemäärä
    username = request.cookies.get('username')
    if username:
        lisaa_pisteet(username, 0)

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
        return arvottu_tieto  # Palautetaan (maa, lentokenttä, latitude, longitude)
    except Exception as e:
        print("Virhe uutta maata ja kenttää arvottaessa:", e)
        return None


@app.route('/get_largest_airport_name')
def get_largest_airport_name():
    arvottu_maa = request.cookies.get('arvottu_maa')

    # Tarkista, että kierroksen_Maa on asetettu evästeisiin
    if arvottu_maa:
        # Haetaan suurimman lentokentän nimi kierroksen_Maa:n perusteella
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT MAX(airport.name) AS largest_airport
            FROM country
            INNER JOIN airport ON country.iso_country = airport.iso_country
            WHERE airport.type = 'large_airport' AND country.name = %s
        """, (arvottu_maa,))
        largest_airport_name = cursor.fetchone()[0]
        cursor.close()
        conn.close()

        return jsonify({'largest_airport_name': largest_airport_name})
    else:
        return jsonify({'largest_airport_name': 'Arvaa ensin maa.'})


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
        cursor.execute("UPDATE game SET points = %s WHERE username = %s", (points, username))
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

    # Jos koordinaatit puuttuvat, arvotaan uudet maat ja koordinaatit
    if arvottu_maa is None or arvottu_latitude is None or arvottu_longitude is None:
        arvottu_tieto = arvo_uusi_maa_ja_kentta()
        arvottu_maa = arvottu_tieto[0]
        arvottu_latitude = str(arvottu_tieto[2])
        arvottu_longitude = str(arvottu_tieto[3])

        # Tallennetaan uudet koordinaatit evästeisiin
        response = make_response(render_template('game.html'))
        response.set_cookie('arvottu_maa', arvottu_maa)
        response.set_cookie('arvottu_latitude', arvottu_latitude)
        response.set_cookie('arvottu_longitude', arvottu_longitude)
        return response

    user_points = hae_kayttajan_pisteet(username)  # Hae käyttäjän pistemäärä

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
                    # Lisää pisteet käyttäjälle
                    pisteet = 0
                    lisaa_pisteet(username, user_points)  # Päivitä pisteet tietokantaan
                    user_points += pisteet  # Päivitä käyttäjän pistemäärä
                    tulos = (
                        f'Arvasit oikein! Oikea maa on: {arvottu_maa}. Keräsit {user_points} pistettä! Aloita uusi peli "Aloita uusi peli" napista.')
                    paivita_hiscore(username, user_points)
                else:
                    # Vähennä 100 pistettä väärästä arvauksesta
                    pisteet = -100
                    lisaa_pisteet(username, user_points + pisteet)  # Päivitä pisteet tietokantaan
                    user_points += pisteet  # Päivitä käyttäjän pistemäärä
                    result_category = 'info'
                    tulos = f'Arvauksesi "{pelaajan_maa}" on väärin. Oikea maa on {etaisyys} km päässä {ilmansuunta}.'

                # Tallenna pisteet evästeisiin
                response = make_response(
                    render_template('game.html', result=tulos, result_category=result_category, points=user_points,
                                    pisteet=pisteet))
                return response
            else:
                tulos = "Maa on kirjoitettu väärin tai sitä ei ole olemassa."
                result_category = 'danger'
        else:
            tulos = "Syötä arvaus."

    # Tallenna pisteet evästeisiin
    user_points = hae_kayttajan_pisteet(username)
    response = make_response(render_template('game.html', result=tulos, result_category=result_category, points=user_points))
    return response



def hae_kayttajan_pisteet(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT points FROM game WHERE username = %s", (username,))
        user_points = cursor.fetchone()[0]
        return user_points
    finally:
        cursor.close()
        conn.close()


@app.route('/start_new_game', methods=['GET'])
def start_new_game():
    try:
        username = request.cookies.get('username')

        # Nollaa käyttäjän pisteet
        lisaa_pisteet(username, 1000)

        # Arvotaan uusi oikea maa ja tallennetaan se tietokantaan käyttäjänimen perusteella
        arvottu_tieto = arvo_uusi_maa_ja_kentta()
        if arvottu_tieto:
            arvottu_maa = arvottu_tieto[0]
            arvottu_latitude = arvottu_tieto[2]
            arvottu_longitude = arvottu_tieto[3]

            # Päivitä uusi maa, koordinaatit ja pistemäärä tietokantaan käyttäjänimen perusteella
            query = "UPDATE game SET kierroksen_Maa = %s, arvottu_latitude = %s, arvottu_longitude = %s WHERE username = %s"
            values = (arvottu_maa, arvottu_latitude, arvottu_longitude, username)
            execute_query(query, values)

            # Poista evästeistä oikean maan koordinaatit
            response = make_response(jsonify({'success': True, 'arvottu_maa': arvottu_maa}))
            response.delete_cookie('arvottu_latitude')
            response.delete_cookie('arvottu_longitude')
            return response
        else:
            response = jsonify({'success': False})
    except Exception as e:
        print("Virhe uutta maata arvottaessa:", e)
        response = jsonify({'success': False})

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

@app.route('/update_correct_answer', methods=['GET'])
def update_correct_answer():
    new_correct_country = arvo_uusi_maa_ja_kentta()  # Arvotaan uusi oikea maa
    if new_correct_country:
        # Tallennetaan uusi oikea maa tietokantaan
        query = "UPDATE game SET kierroksen_Maa = %s"
        execute_query(query, (new_correct_country[0],))
        return jsonify({'success': True, 'message': 'Uusi oikea maa päivitetty onnistuneesti.'})
    else:
        return jsonify({'success': False, 'message': 'Uuden oikean maan päivittäminen epäonnistui.'})


@app.route('/new_game', methods=['GET'])
def new_game():
    try:
        username = request.cookies.get('username')
        arvottu_tieto = arvo_uusi_maa_ja_kentta()
        if arvottu_tieto:
            arvottu_maa = arvottu_tieto[0]
            arvottu_latitude = arvottu_tieto[2]
            arvottu_longitude = arvottu_tieto[3]

            # Päivitä uusi maa, koordinaatit ja pistemäärä tietokantaan käyttäjänimen perusteella
            query = "UPDATE game SET kierroksen_Maa = %s, arvottu_latitude = %s, arvottu_longitude = %s, points = 1000 WHERE username = %s"
            values = (arvottu_maa, arvottu_latitude, arvottu_longitude, username)
            execute_query(query, values)

            # Nollaa käyttäjän pistemäärä
            lisaa_pisteet(username, 1000)

            # Poista evästeistä oikean maan koordinaatit
            response = make_response(jsonify({'success': True, 'arvottu_maa': arvottu_maa}))
            response.delete_cookie('arvottu_latitude')
            response.delete_cookie('arvottu_longitude')
            return response
        else:
            response = jsonify({'success': False})
    except Exception as e:
        print("Virhe uutta maata arvottaessa:", e)
        response = jsonify({'success': False})

    return response


def paivita_hiscore(username, points):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT hiscore FROM game WHERE username = %s", (username,))
        hiscore = cursor.fetchone()[0]

        if points > hiscore:
            cursor.execute("UPDATE game SET hiscore = %s WHERE username = %s", (points, username))
            conn.commit()
    except Exception as e:
        print("Virhe päivittäessä hiscorea:", e)
    finally:
        cursor.close()
        conn.close()


if __name__ == '__main__':
    app.secret_key = 'supersecretkey'
    app.run(debug=True)
