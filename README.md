# 🐧 LinuxCloud — Tu Linux privado en el navegador

Plataforma web donde cada usuario puede registrarse e iniciar su propio entorno Linux
dentro del navegador, basado en **Docker + ttyd + Flask**.

```
usuario → navegador → Flask API → Docker container → ttyd terminal
```

---

## 📁 Estructura del proyecto

```
linuxcloud/
├── backend/
│   ├── app.py              # API Flask principal
│   ├── docker_manager.py   # Gestión de contenedores Docker
│   └── requirements.txt
├── frontend/
│   ├── index.html          # Landing page
│   ├── login.html          # Inicio de sesión
│   ├── register.html       # Registro de usuario
│   ├── dashboard.html      # Panel del usuario
│   ├── css/style.css       # Estilos
│   └── js/
│       ├── app.js          # Cliente API
│       ├── dashboard.js    # Lógica del panel
│       ├── particles.js    # Animación de fondo
│       └── demo-terminal.js# Demo typewriter
├── docker/
│   └── Dockerfile          # Imagen del entorno Linux del usuario
├── nginx/
│   └── nginx.conf          # Configuración Nginx
├── Dockerfile.app          # Imagen del servidor Flask
├── docker-compose.yml      # Orquestación completa
├── .env.example            # Variables de entorno
└── README.md
```

---

## ⚡ Instalación rápida

### Requisitos previos

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y docker.io docker-compose git curl

# Agregar tu usuario al grupo docker (evita usar sudo)
sudo usermod -aG docker $USER
newgrp docker

# Verificar
docker --version          # Docker 24+
docker-compose --version  # 1.29+ o docker compose v2
```

### 1. Clonar / copiar el proyecto

```bash
git clone <repo> linuxcloud
cd linuxcloud
```

### 2. Construir la imagen del entorno Linux

```bash
# Esta imagen es la que verá cada usuario como su "Linux"
docker build -t linuxcloud-env ./docker/
```

### 3. Configurar variables de entorno

```bash
cp .env.example .env
# Editar .env y cambiar JWT_SECRET por algo seguro:
nano .env
```

### 4. Iniciar todo el stack

```bash
docker-compose up -d --build
```

La plataforma estará disponible en **http://TU_IP** (puerto 80).

---

## 🔧 Modo desarrollo (sin Docker Compose)

Si prefieres correr el backend directamente en tu máquina:

```bash
# Instalar dependencias Python
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Variables de entorno
export JWT_SECRET="secreto-desarrollo-123"
export DEBUG=true

# Iniciar Flask
python app.py
```

El frontend está en `frontend/` — sirve estático con Flask o cualquier servidor.

Para probar solo el frontend:
```bash
cd frontend
python3 -m http.server 8080
# Abrir http://localhost:8080
```

---

## 🚪 Puertos utilizados

| Puerto | Servicio |
|--------|----------|
| 80     | Nginx (web principal) |
| 5000   | Flask API |
| 7700-7800 | ttyd de usuarios (uno por usuario activo) |

> ⚠️ Asegúrate de que tu firewall permita el rango **7700-7800** para que los
> usuarios puedan acceder a su terminal desde el navegador.

```bash
# UFW (Ubuntu)
sudo ufw allow 80/tcp
sudo ufw allow 5000/tcp
sudo ufw allow 7700:7800/tcp
```

---

## 🔐 Seguridad

La plataforma implementa:

- **Contraseñas**: bcrypt con factor 12
- **Autenticación**: JWT con expiración de 8 horas
- **Rate limiting**: límites por IP en todos los endpoints
- **Aislamiento**: cada usuario en su propio contenedor Docker
- **Recursos**: límite de CPU (0.5 núcleos) y RAM (256 MB) por contenedor
- **Usuario sin root**: el entorno Linux corre como `linuxuser`
- **Contenedor seguro**: `cap_drop=ALL`, `no-new-privileges`

### Para producción, además:

1. Cambiar `JWT_SECRET` por un valor aleatorio largo
2. Activar HTTPS (ver comentarios en nginx.conf)
3. Usar PostgreSQL en vez de SQLite
4. Implementar un blacklist de tokens con Redis
5. Configurar backups de la base de datos

---

## 📡 API REST

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/register` | Registrar usuario |
| POST | `/api/login` | Iniciar sesión |
| POST | `/api/logout` | Cerrar sesión |
| GET  | `/api/me` | Datos del usuario actual |
| POST | `/api/container/start` | Iniciar contenedor Linux |
| POST | `/api/container/stop` | Detener contenedor |
| GET  | `/api/container/status` | Estado y estadísticas |

**Autenticación**: Header `Authorization: Bearer <token>`

### Ejemplo con curl:

```bash
# Registrar
curl -X POST http://localhost:5000/api/register \
  -H "Content-Type: application/json" \
  -d '{"username":"pepe","email":"pepe@mail.com","password":"segura123"}'

# Login
TOKEN=$(curl -s -X POST http://localhost:5000/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"pepe","password":"segura123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

# Iniciar contenedor
curl -X POST http://localhost:5000/api/container/start \
  -H "Authorization: Bearer $TOKEN"
```

---

## 🖥️ Cómo funciona el terminal web

1. El backend crea un contenedor Docker con **ttyd** escuchando en el puerto **7681 interno**
2. Docker mapea ese puerto a un puerto del host en el rango **7700-7800**
3. El frontend carga un `<iframe>` apuntando a `http://SERVER_IP:PORT`
4. ttyd sirve un cliente **xterm.js** en el navegador conectado al bash del contenedor

### Credenciales del terminal ttyd

```
Usuario: user
Contraseña: cloud123
```

(Puedes cambiarlas en `docker/Dockerfile` en la línea `CMD`)

---

## 🚀 Despliegue en servidor Linux

```bash
# 1. Conectar al servidor
ssh usuario@tu-servidor

# 2. Instalar Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER && newgrp docker

# 3. Clonar proyecto
git clone <repo> /opt/linuxcloud
cd /opt/linuxcloud

# 4. Construir imagen de usuario
docker build -t linuxcloud-env ./docker/

# 5. Configurar entorno
cp .env.example .env
echo "JWT_SECRET=$(openssl rand -hex 32)" >> .env

# 6. Iniciar
docker-compose up -d --build

# 7. Ver logs
docker-compose logs -f app
```

### Systemd service (opcional, para auto-reinicio)

```ini
# /etc/systemd/system/linuxcloud.service
[Unit]
Description=LinuxCloud
After=docker.service
Requires=docker.service

[Service]
WorkingDirectory=/opt/linuxcloud
ExecStart=/usr/bin/docker-compose up
ExecStop=/usr/bin/docker-compose down
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now linuxcloud
```

---

## 🛠️ Comandos útiles

```bash
# Ver contenedores de usuarios activos
docker ps --filter "name=lc_user_"

# Ver logs del backend
docker-compose logs -f app

# Limpiar contenedores huérfanos manualmente
docker rm -f $(docker ps -aq --filter "name=lc_user_")

# Reiniciar el stack
docker-compose restart

# Actualizar y reconstruir
git pull && docker-compose up -d --build
```

---

## ⚙️ Configuración avanzada

Edita `backend/docker_manager.py` para ajustar:

```python
PORT_RANGE_START = 7700   # Puerto inicial
PORT_RANGE_END   = 7800   # Puerto final (= máx usuarios simultáneos)
MAX_CONTAINERS   = 20     # Límite global
CONTAINER_MEMORY = '256m' # RAM por contenedor
CONTAINER_CPU    = 0.5    # CPU por contenedor
```

---

## 📜 Licencia

MIT — libre para uso personal y comercial.
