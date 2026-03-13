"""
LinuxCloud - Backend Principal
API REST con Flask para gestión de usuarios y contenedores Docker
"""
import os
import re
import secrets
from datetime import timedelta
from functools import wraps

import bcrypt
from flask import Flask, request, jsonify, send_from_directory, g
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required,
    get_jwt_identity, get_jwt
)
from flask_sqlalchemy import SQLAlchemy

from docker_manager import DockerManager

# ─── Configuración ────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, '..', 'frontend')

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path='')

app.config.update(
    SQLALCHEMY_DATABASE_URI=f"sqlite:///{os.path.join(BASE_DIR, 'linuxcloud.db')}",
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    JWT_SECRET_KEY=os.environ.get('JWT_SECRET', secrets.token_hex(32)),
    JWT_ACCESS_TOKEN_EXPIRES=timedelta(hours=8),
    JWT_BLACKLIST_ENABLED=True,
    JWT_BLACKLIST_TOKEN_CHECKS=['access'],
)

db = SQLAlchemy(app)
jwt = JWTManager(app)
CORS(app, origins=["*"], supports_credentials=True)

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

docker_mgr = DockerManager()

# ─── Modelos ──────────────────────────────────────────────────────────────────
blacklisted_tokens = set()  # En producción usar Redis

class User(db.Model):
    __tablename__ = 'users'
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(50), unique=True, nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    container_id  = db.Column(db.String(64), nullable=True)
    container_port= db.Column(db.Integer, nullable=True)
    is_active     = db.Column(db.Boolean, default=True)
    created_at    = db.Column(db.DateTime, server_default=db.func.now())

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'container_running': self.container_id is not None,
            'container_port': self.container_port,
        }

# ─── JWT callbacks ────────────────────────────────────────────────────────────
@jwt.token_in_blocklist_loader
def check_token_revoked(jwt_header, jwt_payload):
    return jwt_payload['jti'] in blacklisted_tokens

@jwt.revoked_token_loader
def revoked_token_callback(jwt_header, jwt_payload):
    return jsonify({'error': 'Token revocado. Inicia sesión nuevamente.'}), 401

@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    return jsonify({'error': 'Sesión expirada. Inicia sesión nuevamente.'}), 401

@jwt.invalid_token_loader
def invalid_token_callback(error):
    return jsonify({'error': 'Token inválido.'}), 401

@jwt.unauthorized_loader
def missing_token_callback(error):
    return jsonify({'error': 'No autorizado.'}), 401

# ─── Helpers ──────────────────────────────────────────────────────────────────
def validate_username(username):
    return re.match(r'^[a-zA-Z0-9_]{3,20}$', username) is not None

def validate_email(email):
    return re.match(r'^[^@]+@[^@]+\.[^@]+$', email) is not None

def validate_password(password):
    return len(password) >= 8

# ─── Rutas estáticas ──────────────────────────────────────────────────────────
@app.route('/')
def index():
    return send_from_directory(FRONTEND_DIR, 'index.html')

@app.route('/<path:path>')
def static_files(path):
    if os.path.exists(os.path.join(FRONTEND_DIR, path)):
        return send_from_directory(FRONTEND_DIR, path)
    return send_from_directory(FRONTEND_DIR, 'index.html')

# ─── Auth API ─────────────────────────────────────────────────────────────────
@app.route('/api/register', methods=['POST'])
@limiter.limit("5 per minute")
def register():
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    email    = data.get('email', '').strip().lower()
    password = data.get('password', '')

    # Validaciones
    errors = []
    if not validate_username(username):
        errors.append('El usuario debe tener 3-20 caracteres alfanuméricos o guión bajo.')
    if not validate_email(email):
        errors.append('Email inválido.')
    if not validate_password(password):
        errors.append('La contraseña debe tener al menos 8 caracteres.')
    if errors:
        return jsonify({'error': ' '.join(errors)}), 400

    # Verificar duplicados
    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'El nombre de usuario ya está en uso.'}), 409
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'El email ya está registrado.'}), 409

    # Crear usuario
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12))
    user = User(username=username, email=email, password_hash=pw_hash.decode())
    db.session.add(user)
    db.session.commit()

    token = create_access_token(identity=str(user.id))
    return jsonify({'message': 'Cuenta creada exitosamente.', 'token': token, 'user': user.to_dict()}), 201


@app.route('/api/login', methods=['POST'])
@limiter.limit("10 per minute")
def login():
    data     = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': 'Usuario y contraseña son requeridos.'}), 400

    user = User.query.filter_by(username=username).first()
    if not user or not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
        return jsonify({'error': 'Credenciales incorrectas.'}), 401

    if not user.is_active:
        return jsonify({'error': 'Cuenta desactivada.'}), 403

    token = create_access_token(identity=str(user.id))
    return jsonify({'message': 'Sesión iniciada.', 'token': token, 'user': user.to_dict()}), 200


@app.route('/api/logout', methods=['POST'])
@jwt_required()
def logout():
    jti = get_jwt()['jti']
    blacklisted_tokens.add(jti)

    # Si hay contenedor activo, detenerlo
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    if user and user.container_id:
        try:
            docker_mgr.stop_container(user.container_id)
        except Exception:
            pass
        user.container_id   = None
        user.container_port = None
        db.session.commit()

    return jsonify({'message': 'Sesión cerrada correctamente.'}), 200


@app.route('/api/me', methods=['GET'])
@jwt_required()
def me():
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'Usuario no encontrado.'}), 404
    return jsonify({'user': user.to_dict()}), 200

# ─── Container API ────────────────────────────────────────────────────────────
@app.route('/api/container/start', methods=['POST'])
@jwt_required()
@limiter.limit("5 per minute")
def start_container():
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'Usuario no encontrado.'}), 404

    # Si ya tiene contenedor activo, verificarlo
    if user.container_id:
        is_running = docker_mgr.is_container_running(user.container_id)
        if is_running:
            return jsonify({
                'message': 'El contenedor ya está activo.',
                'container_port': user.container_port,
                'status': 'running'
            }), 200
        else:
            # Limpiar referencia obsoleta
            user.container_id   = None
            user.container_port = None
            db.session.commit()

    # Crear nuevo contenedor
    try:
        container_id, port = docker_mgr.create_container(user.id, user.username)
        user.container_id   = container_id
        user.container_port = port
        db.session.commit()

        return jsonify({
            'message': 'Entorno Linux iniciado.',
            'container_port': port,
            'status': 'running'
        }), 200
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 503
    except Exception as e:
        app.logger.error(f'Error creating container for user {user_id}: {e}')
        return jsonify({'error': 'Error interno al crear el contenedor.'}), 500


@app.route('/api/container/stop', methods=['POST'])
@jwt_required()
def stop_container():
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'Usuario no encontrado.'}), 404

    if not user.container_id:
        return jsonify({'message': 'No hay contenedor activo.'}), 200

    try:
        docker_mgr.stop_container(user.container_id)
    except Exception as e:
        app.logger.warning(f'Error stopping container {user.container_id}: {e}')

    user.container_id   = None
    user.container_port = None
    db.session.commit()

    return jsonify({'message': 'Entorno Linux detenido correctamente.', 'status': 'stopped'}), 200


@app.route('/api/container/status', methods=['GET'])
@jwt_required()
def container_status():
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'Usuario no encontrado.'}), 404

    if not user.container_id:
        return jsonify({'status': 'stopped', 'container_port': None}), 200

    is_running = docker_mgr.is_container_running(user.container_id)
    if not is_running:
        user.container_id   = None
        user.container_port = None
        db.session.commit()
        return jsonify({'status': 'stopped', 'container_port': None}), 200

    stats = docker_mgr.get_container_stats(user.container_id)
    return jsonify({
        'status': 'running',
        'container_port': user.container_port,
        'stats': stats
    }), 200


@app.route('/api/admin/users', methods=['GET'])
@jwt_required()
def admin_users():
    """Solo para debug/admin — en producción proteger mejor."""
    users = User.query.all()
    return jsonify({'users': [u.to_dict() for u in users], 'total': len(users)}), 200


# ─── Error handlers ───────────────────────────────────────────────────────────
@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Ruta no encontrada.'}), 404

@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({'error': 'Demasiadas solicitudes. Intenta más tarde.'}), 429

@app.errorhandler(500)
def internal_error(e):
    return jsonify({'error': 'Error interno del servidor.'}), 500

# ─── Init ─────────────────────────────────────────────────────────────────────
def init_app():
    with app.app_context():
        db.create_all()
        app.logger.info('Base de datos inicializada.')

    # Limpiar contenedores huérfanos al iniciar
    try:
        docker_mgr.cleanup_orphaned_containers()
        app.logger.info('Limpieza de contenedores completada.')
    except Exception as e:
        app.logger.warning(f'No se pudo limpiar contenedores: {e}')


if __name__ == '__main__':
    init_app()
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
