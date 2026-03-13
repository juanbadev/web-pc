"""
DockerManager - Gestión del ciclo de vida de contenedores Linux por usuario
"""
import docker
import logging
import threading
import time

logger = logging.getLogger(__name__)

# ─── Configuración ────────────────────────────────────────────────────────────
CONTAINER_IMAGE    = 'linuxcloud-env'        # Imagen construida desde docker/Dockerfile
PORT_RANGE_START   = 7700                    # Puerto inicial para ttyd
PORT_RANGE_END     = 7800                    # Puerto final (100 usuarios max)
CONTAINER_PREFIX   = 'lc_user_'             # Prefijo para identificar contenedores
MAX_CONTAINERS     = 20                      # Límite de contenedores simultáneos
CONTAINER_MEMORY   = '256m'                 # RAM por contenedor
CONTAINER_CPU      = 0.5                     # CPU por contenedor (fracción de núcleo)
IDLE_TIMEOUT       = 3600                    # Segundos sin actividad → auto-stop (1h)


class DockerManager:
    def __init__(self):
        try:
            self.client = docker.from_env()
            self.client.ping()
            logger.info('Conexión a Docker establecida.')
        except Exception as e:
            logger.error(f'No se pudo conectar a Docker: {e}')
            raise RuntimeError(f'Docker no disponible: {e}')

        self._lock = threading.Lock()
        self._used_ports: set[int] = set()
        self._refresh_used_ports()

    # ─── Gestión de puertos ───────────────────────────────────────────────────
    def _refresh_used_ports(self):
        """Sincronizar puertos usados con contenedores activos."""
        try:
            containers = self.client.containers.list(
                filters={'name': CONTAINER_PREFIX}
            )
            self._used_ports = set()
            for c in containers:
                for port_data in c.ports.values():
                    if port_data:
                        for p in port_data:
                            self._used_ports.add(int(p['HostPort']))
        except Exception as e:
            logger.warning(f'Error sincronizando puertos: {e}')

    def _get_free_port(self) -> int:
        """Obtener primer puerto disponible en el rango configurado."""
        self._refresh_used_ports()
        for port in range(PORT_RANGE_START, PORT_RANGE_END):
            if port not in self._used_ports:
                return port
        raise RuntimeError(
            f'No hay puertos disponibles ({PORT_RANGE_START}-{PORT_RANGE_END}). '
            f'Servidor al límite de capacidad.'
        )

    # ─── Creación de contenedores ─────────────────────────────────────────────
    def create_container(self, user_id: int, username: str) -> tuple[str, int]:
        """
        Crear y arrancar un contenedor Linux para el usuario.
        Retorna (container_id, host_port).
        """
        with self._lock:
            # Verificar límite global
            running = self.client.containers.list(
                filters={'name': CONTAINER_PREFIX}
            )
            if len(running) >= MAX_CONTAINERS:
                raise RuntimeError(
                    f'Límite máximo de {MAX_CONTAINERS} entornos simultáneos alcanzado. '
                    f'Intenta más tarde.'
                )

            # Eliminar contenedor previo del usuario si existe
            container_name = f'{CONTAINER_PREFIX}{user_id}'
            self._force_remove_by_name(container_name)

            port = self._get_free_port()
            self._used_ports.add(port)

        try:
            container = self.client.containers.run(
                image=CONTAINER_IMAGE,
                name=container_name,
                detach=True,
                remove=False,  # Remover manualmente para mayor control
                ports={'7681/tcp': port},
                mem_limit=CONTAINER_MEMORY,
                nano_cpus=int(CONTAINER_CPU * 1e9),
                network_mode='bridge',
                labels={
                    'linuxcloud': 'true',
                    'user_id': str(user_id),
                    'username': username,
                    'created_at': str(int(time.time())),
                },
                # Seguridad adicional
                cap_drop=['ALL'],
                cap_add=['CHOWN', 'SETUID', 'SETGID'],
                security_opt=['no-new-privileges:true'],
                read_only=False,
                tmpfs={'/tmp': 'size=64m'},
            )

            # Esperar a que ttyd esté listo
            time.sleep(1.5)

            logger.info(
                f'Contenedor creado para usuario {username} (id={user_id}) '
                f'en puerto {port}: {container.short_id}'
            )
            return container.id, port

        except Exception as e:
            with self._lock:
                self._used_ports.discard(port)
            logger.error(f'Error creando contenedor para user {user_id}: {e}')
            raise

    # ─── Control de contenedores ──────────────────────────────────────────────
    def stop_container(self, container_id: str):
        """Detener y eliminar contenedor."""
        try:
            container = self.client.containers.get(container_id)
            port = self._get_container_port(container)
            container.stop(timeout=5)
            container.remove(force=True)
            with self._lock:
                if port:
                    self._used_ports.discard(port)
            logger.info(f'Contenedor {container_id[:12]} detenido y eliminado.')
        except docker.errors.NotFound:
            logger.warning(f'Contenedor {container_id[:12]} no encontrado (ya eliminado).')
        except Exception as e:
            logger.error(f'Error deteniendo contenedor {container_id[:12]}: {e}')
            raise

    def is_container_running(self, container_id: str) -> bool:
        """Verificar si el contenedor está activo."""
        try:
            container = self.client.containers.get(container_id)
            return container.status == 'running'
        except docker.errors.NotFound:
            return False
        except Exception:
            return False

    def get_container_stats(self, container_id: str) -> dict:
        """Obtener estadísticas básicas del contenedor."""
        try:
            container = self.client.containers.get(container_id)
            stats = container.stats(stream=False)

            # CPU %
            cpu_delta  = stats['cpu_stats']['cpu_usage']['total_usage'] \
                       - stats['precpu_stats']['cpu_usage']['total_usage']
            sys_delta  = stats['cpu_stats']['system_cpu_usage'] \
                       - stats['precpu_stats']['system_cpu_usage']
            num_cpus   = stats['cpu_stats'].get('online_cpus', 1)
            cpu_pct    = (cpu_delta / sys_delta) * num_cpus * 100.0 if sys_delta > 0 else 0.0

            # Memoria
            mem_usage  = stats['memory_stats'].get('usage', 0)
            mem_limit  = stats['memory_stats'].get('limit', 1)
            mem_pct    = (mem_usage / mem_limit) * 100.0

            return {
                'cpu_percent': round(cpu_pct, 1),
                'mem_usage_mb': round(mem_usage / 1024 / 1024, 1),
                'mem_limit_mb': round(mem_limit / 1024 / 1024, 1),
                'mem_percent': round(mem_pct, 1),
                'status': container.status,
            }
        except Exception as e:
            logger.warning(f'Error obteniendo stats de {container_id[:12]}: {e}')
            return {'cpu_percent': 0, 'mem_usage_mb': 0, 'mem_limit_mb': 256, 'mem_percent': 0, 'status': 'unknown'}

    # ─── Limpieza ─────────────────────────────────────────────────────────────
    def _force_remove_by_name(self, name: str):
        """Eliminar contenedor por nombre si existe."""
        try:
            old = self.client.containers.get(name)
            port = self._get_container_port(old)
            old.remove(force=True)
            if port:
                self._used_ports.discard(port)
            logger.info(f'Contenedor previo "{name}" eliminado.')
        except docker.errors.NotFound:
            pass

    def _get_container_port(self, container) -> int | None:
        """Extraer puerto host de un contenedor."""
        try:
            ports = container.ports.get('7681/tcp')
            if ports:
                return int(ports[0]['HostPort'])
        except Exception:
            pass
        return None

    def cleanup_orphaned_containers(self):
        """Eliminar contenedores huérfanos de sesiones anteriores."""
        try:
            containers = self.client.containers.list(
                all=True,
                filters={'name': CONTAINER_PREFIX, 'label': 'linuxcloud=true'}
            )
            for c in containers:
                logger.info(f'Eliminando contenedor huérfano: {c.name}')
                c.remove(force=True)
            self._used_ports.clear()
            logger.info(f'Limpieza completada: {len(containers)} contenedores eliminados.')
        except Exception as e:
            logger.warning(f'Error en limpieza: {e}')

    def list_active_containers(self) -> list[dict]:
        """Listar todos los contenedores activos de linuxcloud."""
        try:
            containers = self.client.containers.list(
                filters={'label': 'linuxcloud=true'}
            )
            result = []
            for c in containers:
                result.append({
                    'id': c.short_id,
                    'name': c.name,
                    'status': c.status,
                    'user_id': c.labels.get('user_id', '?'),
                    'username': c.labels.get('username', '?'),
                    'created_at': c.labels.get('created_at', '?'),
                    'port': self._get_container_port(c),
                })
            return result
        except Exception as e:
            logger.warning(f'Error listando contenedores: {e}')
            return []
