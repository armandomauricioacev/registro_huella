from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import mysql.connector
from mysql.connector import Error
from datetime import datetime
import pytz

app = Flask(__name__)
CORS(app)

# Configuración de la base de datos Railway
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
        id_huella,           # HUELLAS COMO INT
        '2000-01-01',        # fecha_nacimiento
        1,                   # areas_id
        1,                   # puesto_id
        fecha_hora,          # fecha_registro (hora México)
        1                    # status_id
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

@app.route('/api/nombre/<int:id_huella>', methods=['GET'])
def get_nombre(id_huella):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT nombre, id, fecha_registro
        FROM usuario
        WHERE huella = %s
    """, (id_huella,))
    result = cursor.fetchone()
    cursor.close()
    db.close()
    if result:
        return jsonify({
            'status': 'ok',
            'nombre': result['nombre'],
            'id_huella': id_huella,
            'id_usuario': result['id'],
            'fecha_registro': result['fecha_registro']
        })
    else:
        return jsonify({'status': 'not_found'})

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

    # Revisar último acceso
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

# ===================== ADMIN - Panel Web =====================

@app.route("/admin/menu")
def admin_menu():
    return render_template("menu.html")

@app.route('/admin/usuarios', methods=['GET'])
def admin_usuarios():
    id_buscar = request.args.get('id')
    nombre_buscar = request.args.get('nombre')

    db = get_db()
    cursor = db.cursor(dictionary=True)
    query = """
        SELECT id, nombre, huella, fecha_registro
        FROM usuario
    """
    filters = []
    values = []
    if id_buscar:
        filters.append("id = %s")
        values.append(id_buscar)
    if nombre_buscar:
        filters.append("nombre LIKE %s")
        values.append(f"%{nombre_buscar}%")
    if filters:
        query += " WHERE " + " AND ".join(filters)
    query += " ORDER BY id"

    cursor.execute(query, tuple(values))
    usuarios = cursor.fetchall()
    cursor.close()
    db.close()
    return render_template('usuarios.html', usuarios=usuarios, id_buscar=id_buscar or "", nombre_buscar=nombre_buscar or "")

@app.route('/admin/accesos')
def admin_accesos():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT ae.id, u.nombre, ae.tipo, ae.fecha_acceso 
        FROM accesos_empleados ae
        JOIN usuario u ON ae.usuario_id = u.id
        ORDER BY ae.fecha_acceso DESC
    """)
    accesos = cursor.fetchall()
    cursor.close()
    db.close()
    return render_template("accesos.html", accesos=accesos, usuario=None)

@app.route('/admin/accesos/<int:usuario_id>')
def accesos_por_usuario(usuario_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT ae.id, u.nombre, ae.tipo, ae.fecha_acceso 
        FROM accesos_empleados ae
        JOIN usuario u ON ae.usuario_id = u.id
        WHERE u.id = %s
        ORDER BY ae.fecha_acceso DESC
    """, (usuario_id,))
    accesos = cursor.fetchall()
    cursor.execute("SELECT nombre FROM usuario WHERE id=%s", (usuario_id,))
    usuario = cursor.fetchone()
    cursor.close()
    db.close()
    return render_template("accesos.html", accesos=accesos, usuario=usuario)

@app.route('/admin/huellas')
def admin_huellas():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT h.id_huella, u.nombre, u.id as id_persona, h.fecha_registro
        FROM huellas h
        LEFT JOIN usuario u ON h.id_persona = u.id
        ORDER BY h.id_huella
    """)
    huellas = cursor.fetchall()
    cursor.close()
    db.close()
    return render_template("huellas.html", huellas=huellas)

@app.route("/")
def index():
    return "<h1>API biométrica corriendo en Railway 🚄<br><a href='/admin/menu'>Ir al panel admin</a></h1>"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
