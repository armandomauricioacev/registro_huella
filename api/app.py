from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import mysql.connector
from datetime import datetime
import pytz

app = Flask(__name__)
CORS(app)

MYSQL_CONFIG = {
    "host": "crossover.proxy.rlwy.net",
    "port": 27645,
    "user": "root",
    "password": "QZfJLpAfqssdkkNaRuvyvIEWQKwkdsrn",
    "database": "railway"
}
MX_TZ = pytz.timezone("America/Mexico_City")

def get_db():
    return mysql.connector.connect(**MYSQL_CONFIG)

def fecha_hora_mexico():
    now_utc = datetime.now(pytz.UTC)
    now_mx = now_utc.astimezone(MX_TZ)
    return now_mx.strftime("%Y-%m-%d %H:%M:%S")

# ----------- VISTAS WEB ------------
@app.route("/")
def index():
    return "<h1>API biométrica corriendo en Railway 🚄<br><a href='/admin/menu'>Ir al panel admin</a></h1>"

@app.route("/admin/menu")
def admin_menu():
    return render_template("menu.html")

@app.route("/admin/usuarios")
def admin_usuarios():
    return render_template("usuarios.html")

@app.route('/admin/accesos')
@app.route('/admin/accesos/<int:usuario_id>')
def admin_accesos(usuario_id=None):
    return render_template("accesos.html", usuario_id=usuario_id)

# ----------- ENDPOINTS API ------------

# --- Obtener todos los usuarios ---
@app.route('/api/usuarios', methods=['GET'])
def get_usuarios():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT id, nombre, huella, fecha_registro FROM usuario ORDER BY id")
    result = cursor.fetchall()
    cursor.close()
    db.close()
    return jsonify(result)

# --- Obtener todos los accesos ---
@app.route('/api/accesos', methods=['GET'])
def get_accesos():
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

# --- Obtener accesos por usuario ---
@app.route('/api/accesos/<int:usuario_id>', methods=['GET'])
def get_accesos_usuario(usuario_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT ae.id, u.nombre, ae.tipo, ae.fecha_acceso 
        FROM accesos_empleados ae
        JOIN usuario u ON ae.usuario_id = u.id
        WHERE u.id = %s
        ORDER BY ae.fecha_acceso DESC
        LIMIT 50
    """, (usuario_id,))
    accesos = cursor.fetchall()
    cursor.close()
    db.close()
    return jsonify(accesos)

# --- Registrar nuevo usuario (huella) ---
@app.route('/api/registrar', methods=['POST'])
def registrar():
    data = request.json
    id_huella = int(data.get('id_huella'))
    nombre = data.get('nombre', "Pendiente")
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
        b'', nombre, f"{nombre.lower()}@example.com", "Generico", "Generico",
        id_huella, '2000-01-01', 1, 1, fecha_hora, 1
    )
    cursor.execute(sql, values)
    db.commit()
    cursor.close()
    db.close()
    return jsonify({'status': 'registrado', 'nombre': nombre, 'id_huella': id_huella, 'fecha_registro': fecha_hora})

# --- Registrar acceso (entrada/salida) ---
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

# --- Editar nombre de usuario ---
@app.route('/api/usuario/actualizar_nombre', methods=['POST'])
def actualizar_nombre():
    data = request.json
    id_usuario = int(data.get('id_usuario'))
    nombre = data.get('nombre', "Pendiente")
    db = get_db()
    cursor = db.cursor()
    cursor.execute("UPDATE usuario SET nombre=%s WHERE id=%s", (nombre, id_usuario))
    db.commit()
    cursor.close()
    db.close()
    return jsonify(True)

# --- Eliminar usuario (y marca huella para borrar en sensor) ---
@app.route('/api/usuario/eliminar', methods=['POST'])
def eliminar_usuario():
    data = request.json
    id_usuario = int(data.get('id_usuario'))
    db = get_db()
    cursor = db.cursor(dictionary=True)
    # Obtener id_huella antes de borrar
    cursor.execute("SELECT huella FROM usuario WHERE id=%s", (id_usuario,))
    result = cursor.fetchone()
    if not result:
        cursor.close()
        db.close()
        return jsonify({'status': 'not_found'})
    id_huella = result['huella']
    # Borrar usuario (ON DELETE CASCADE borra accesos)
    cursor.execute("DELETE FROM usuario WHERE id=%s", (id_usuario,))
    db.commit()
    # Marca para borrar en el sensor: agrega a tabla
    cursor.execute("""
        INSERT INTO huellas_a_borrar (id_huella, fecha_solicitud, borrado) 
        VALUES (%s, %s, 0)
        ON DUPLICATE KEY UPDATE borrado=0, fecha_solicitud=%s
    """, (id_huella, fecha_hora_mexico(), fecha_hora_mexico()))
    db.commit()
    cursor.close()
    db.close()
    return jsonify({'status': 'eliminado', 'id_huella': id_huella})

# --- Consultar huellas pendientes por borrar (para ESP32) ---
@app.route('/api/huella/pendientes_borrar', methods=['GET'])
def huellas_pendientes_borrar():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT id_huella FROM huellas_a_borrar WHERE borrado=0")
    pendientes = [row['id_huella'] for row in cursor.fetchall()]
    cursor.close()
    db.close()
    return jsonify({'huellas': pendientes})

# --- Marcar huella como borrada (llamado por ESP32 tras borrar físicamente) ---
@app.route('/api/huella/marcar_borrada', methods=['POST'])
def marcar_huella_borrada():
    data = request.json
    id_huella = int(data.get('id_huella'))
    db = get_db()
    cursor = db.cursor()
    cursor.execute("UPDATE huellas_a_borrar SET borrado=1 WHERE id_huella=%s", (id_huella,))
    db.commit()
    cursor.close()
    db.close()
    return jsonify({'status': 'ok'})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
