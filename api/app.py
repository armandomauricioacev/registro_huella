from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import mysql.connector
from mysql.connector import Error
from datetime import datetime
import pytz

app = Flask(__name__)
CORS(app)

# Configuración de la base de datos
MYSQL_CONFIG = {
    "host": "crossover.proxy.rlwy.net",
    "port": 27645,
    "user": "root",
    "password": "QZfJLpAfqssdkkNaRuvyvIEWQKwkdsrn",
    "database": "railway"
}

# Zona horaria de CDMX
MX_TZ = pytz.timezone("America/Mexico_City")

def get_db():
    return mysql.connector.connect(**MYSQL_CONFIG)

def fecha_hora_mexico():
    now_utc = datetime.now(pytz.UTC)
    now_mx = now_utc.astimezone(MX_TZ)
    return now_mx.strftime("%Y-%m-%d %H:%M:%S")

# ===================== API para registro y accesos =====================

@app.route('/api/registrar', methods=['POST'])
def registrar():
    data = request.json
    id_huella = int(data.get('id_huella'))
    nombre = data.get('nombre')

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT id FROM usuario WHERE huella=%s", (id_huella,))
    if cursor.fetchone():
        cursor.close()
        db.close()
        return jsonify({'status': 'ya_registrado'})

    fecha_hora = fecha_hora_mexico()
    sql = """
    INSERT INTO usuario (
        foto_usuario, nombre, correo, apellido_p, apellido_m, huella,
        fecha_nacimiento, areas_id, puesto_id, fecha_registro, status_id
    ) VALUES (
        %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s
    )
    """
    values = (
        b'',  # foto_usuario (vacío)
        nombre,
        f"{nombre.lower()}@example.com",
        "Generico",
        "Generico",
        id_huella,
        '2000-01-01',
        1,  # areas_id
        1,  # puesto_id
        fecha_hora,
        1   # status_id
    )
    cursor.execute(sql, values)
    db.commit()
    cursor.close()
    db.close()
    return jsonify({
        'status': 'registrado',
        'nombre': nombre,
        'id_huella': id_huella,
        'fecha_registro': fecha_hora
    })

@app.route('/api/usuario/actualizar_nombre', methods=['POST'])
def actualizar_nombre_usuario():
    data = request.json
    usuario_id = data.get('id')
    nuevo_nombre = data.get('nombre')
    db = get_db()
    cursor = db.cursor()
    cursor.execute("UPDATE usuario SET nombre=%s WHERE id=%s", (nuevo_nombre, usuario_id))
    db.commit()
    cursor.close()
    db.close()
    return jsonify({'status': 'ok'})

@app.route('/api/acceso', methods=['POST'])
def registrar_acceso():
    data = request.json
    id_huella = int(data.get('id_huella'))

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT id, nombre FROM usuario WHERE huella=%s", (id_huella,))
    usuario = cursor.fetchone()
    if not usuario:
        cursor.close()
        db.close()
        return jsonify({'status': 'not_found', 'mensaje': 'Huella reconocida, pero sin nombre asociado.'})

    usuario_id = usuario['id']
    nombre = usuario['nombre']

    cursor.execute("""
        SELECT tipo FROM accesos_empleados
        WHERE usuario_id=%s
        ORDER BY fecha_acceso DESC
        LIMIT 1
    """, (usuario_id,))
    last = cursor.fetchone()

    if not last or last['tipo'] == 'salida':
        tipo = 'entrada'
        mensaje = f"¡Bienvenido, {nombre}!"
    else:
        tipo = 'salida'
        mensaje = f"Hasta pronto, {nombre}!"

    now = fecha_hora_mexico()
    cursor.execute("""
        INSERT INTO accesos_empleados (usuario_id, status_id, tipo, fecha_acceso)
        VALUES (%s, %s, %s, %s)
    """, (usuario_id, 1, tipo, now))
    db.commit()

    cursor.close()
    db.close()
    return jsonify({'status': 'ok', 'mensaje': mensaje, 'tipo': tipo, 'fecha': now})

# ===================== API para consulta en tiempo real =====================

@app.route('/api/usuarios', methods=['GET'])
def get_usuarios():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, nombre, huella, fecha_registro
        FROM usuario
        ORDER BY id
    """)
    result = cursor.fetchall()
    cursor.close()
    db.close()
    return jsonify(result)

@app.route('/api/accesos', methods=['GET'])
def api_accesos():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT ae.id, u.nombre, ae.tipo, ae.fecha_acceso 
        FROM accesos_empleados ae
        JOIN usuario u ON ae.usuario_id = u.id
        ORDER BY ae.fecha_acceso DESC
        LIMIT 100
    """)
    accesos = cursor.fetchall()
    cursor.close()
    db.close()
    return jsonify(accesos)

# ===================== ADMIN - Panel Web =====================

@app.route("/admin/menu")
def admin_menu():
    return render_template("menu.html")

@app.route('/admin/usuarios')
def admin_usuarios():
    return render_template('usuarios.html')

@app.route('/admin/accesos')
def admin_accesos():
    return render_template('accesos.html')

@app.route("/")
def index():
    return "<h1>API biométrica corriendo en Railway 🚄<br><a href='/admin/menu'>Ir al panel admin</a></h1>"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
