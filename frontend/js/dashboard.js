/**
 * LinuxCloud - Dashboard Controller
 * Lógica completa del panel de usuario
 */

(async () => {

  // ── Auth guard ──────────────────────────────────────────
  if (!api.isLoggedIn()) {
    window.location.href = '/login.html';
    return;
  }

  // ── State ───────────────────────────────────────────────
  let user          = api.getUser() || {};
  let containerPort = null;
  let isRunning     = false;
  let statsInterval = null;
  let HOST          = window.location.hostname;  // IP/dominio del servidor

  // ── DOM refs ─────────────────────────────────────────────
  const welcomeUser    = document.getElementById('welcomeUser');
  const userAvatarSide = document.getElementById('userAvatarSide');
  const usernameSide   = document.getElementById('usernameSide');
  const statusDot      = document.getElementById('statusDot');
  const statusText     = document.getElementById('statusText');
  const ctrlDesc       = document.getElementById('ctrlDesc');
  const controlCard    = document.querySelector('.control-card');

  const startBtn       = document.getElementById('startBtn');
  const stopBtn        = document.getElementById('stopBtn');
  const openTermBtn    = document.getElementById('openTermBtn');
  const statsRow       = document.getElementById('statsRow');
  const activityList   = document.getElementById('activityList');
  const termContainer  = document.getElementById('termContainer');
  const termPlaceholder= document.getElementById('termPlaceholder');
  const termFrame      = document.getElementById('terminalFrame');
  const logoutBtn      = document.getElementById('logoutBtn');
  const startFromTermBtn = document.getElementById('startFromTermBtn');
  const reloadTermBtn  = document.getElementById('reloadTermBtn');
  const fullscreenBtn  = document.getElementById('fullscreenBtn');

  // ── Init UI ──────────────────────────────────────────────
  function initUserUI() {
    const name = user.username || 'usuario';
    welcomeUser.textContent    = name;
    userAvatarSide.textContent = name[0].toUpperCase();
    usernameSide.textContent   = name;
  }

  // ── Activity log ─────────────────────────────────────────
  function addLog(msg, type = 'info') {
    const li = document.createElement('li');
    const now = new Date().toLocaleTimeString('es');
    li.className = `log-item log-${type}`;
    li.textContent = `[${now}] ${msg}`;
    activityList.prepend(li);
    // Limitar a 20 entradas
    while (activityList.children.length > 20) {
      activityList.lastChild.remove();
    }
  }

  // ── Status update ────────────────────────────────────────
  function setStatus(state) {
    statusDot.className = `status-dot ${state}`;
    if (state === 'running') {
      statusText.textContent = 'Activo';
      controlCard.classList.add('running');
    } else if (state === 'loading') {
      statusText.textContent = 'Iniciando…';
      controlCard.classList.remove('running');
    } else {
      statusText.textContent = 'Detenido';
      controlCard.classList.remove('running');
    }
  }

  function setRunningUI(running, port = null) {
    isRunning     = running;
    containerPort = port;

    startBtn.classList.toggle('hidden', running);
    stopBtn.classList.toggle('hidden', !running);
    openTermBtn.classList.toggle('hidden', !running);
    statsRow.style.display = running ? 'grid' : 'none';

    if (running && port) {
      setStatus('running');
      ctrlDesc.textContent = `En ejecución en puerto ${port} · Ubuntu 22.04 · Docker`;
      document.getElementById('statPort').textContent = port;
      document.getElementById('statStatus').textContent = 'running';
      // Mostrar terminal si panel activo
      renderTerminal(port);
    } else {
      setStatus('stopped');
      ctrlDesc.textContent = 'Contenedor Docker con Ubuntu 22.04 + terminal web.';
      hideTerminal();
    }
  }

  // ── Terminal iframe ───────────────────────────────────────
  function getTerminalUrl(port) {
    // ttyd URL — ajusta si usas HTTPS
    const protocol = window.location.protocol;
    return `${protocol}//${HOST}:${port}`;
  }

  function renderTerminal(port) {
    const url = getTerminalUrl(port);
    termPlaceholder.classList.add('hidden');
    termFrame.classList.remove('hidden');
    if (termFrame.src !== url) {
      termFrame.src = url;
    }
    startFromTermBtn.classList.add('hidden');
  }

  function hideTerminal() {
    termPlaceholder.classList.remove('hidden');
    termFrame.classList.add('hidden');
    termFrame.src = '';
    startFromTermBtn.classList.remove('hidden');
  }

  // ── Stats polling ─────────────────────────────────────────
  async function pollStats() {
    try {
      const data = await api.get('/api/container/status');
      if (data.status === 'running' && data.stats) {
        const s = data.stats;
        document.getElementById('statCpu').textContent = s.cpu_percent + '%';
        document.getElementById('statMem').textContent = `${s.mem_usage_mb}MB`;
        document.getElementById('statStatus').textContent = s.status;
      } else if (data.status === 'stopped') {
        // Contenedor se detuvo externamente
        setRunningUI(false);
        stopStatsPolling();
        addLog('El contenedor se detuvo.', 'warning');
      }
    } catch (_) {}
  }

  function startStatsPolling() {
    stopStatsPolling();
    statsInterval = setInterval(pollStats, 5000);
  }

  function stopStatsPolling() {
    if (statsInterval) { clearInterval(statsInterval); statsInterval = null; }
  }

  // ── Container actions ─────────────────────────────────────
  async function startContainer() {
    startBtn.disabled = true;
    setStatus('loading');
    addLog('Iniciando contenedor Docker…', 'info');

    try {
      const data = await api.post('/api/container/start', {});
      const port = data.container_port;
      setRunningUI(true, port);
      startStatsPolling();
      addLog(`Entorno Linux activo en puerto ${port}.`, 'success');
    } catch (err) {
      setStatus('stopped');
      addLog(`Error al iniciar: ${err.message}`, 'error');
      alert(`Error: ${err.message}`);
    } finally {
      startBtn.disabled = false;
    }
  }

  async function stopContainer() {
    stopBtn.disabled = true;
    addLog('Deteniendo contenedor…', 'info');

    try {
      await api.post('/api/container/stop', {});
      setRunningUI(false);
      stopStatsPolling();
      addLog('Entorno Linux detenido.', 'success');
    } catch (err) {
      addLog(`Error al detener: ${err.message}`, 'error');
    } finally {
      stopBtn.disabled = false;
    }
  }

  // ── Panel navigation ──────────────────────────────────────
  document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', (e) => {
      e.preventDefault();
      const panelId = item.dataset.panel;

      document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
      item.classList.add('active');

      document.querySelectorAll('.dash-panel').forEach(p => p.classList.remove('active'));
      document.getElementById(`panel-${panelId}`).classList.add('active');

      // Si abrimos terminal y hay contenedor activo
      if (panelId === 'terminal' && isRunning && containerPort) {
        renderTerminal(containerPort);
      }
    });
  });

  // ── Event listeners ───────────────────────────────────────
  startBtn.addEventListener('click', startContainer);
  stopBtn.addEventListener('click', stopContainer);
  startFromTermBtn.addEventListener('click', () => {
    // Navegar a panel home y lanzar
    document.querySelector('[data-panel="home"]').click();
    setTimeout(startContainer, 100);
  });

  openTermBtn.addEventListener('click', () => {
    document.querySelector('[data-panel="terminal"]').click();
  });

  reloadTermBtn.addEventListener('click', () => {
    if (isRunning && containerPort) {
      termFrame.src = getTerminalUrl(containerPort);
    }
  });

  fullscreenBtn.addEventListener('click', () => {
    if (termFrame.requestFullscreen) termFrame.requestFullscreen();
    else if (termFrame.webkitRequestFullscreen) termFrame.webkitRequestFullscreen();
  });

  logoutBtn.addEventListener('click', async () => {
    if (isRunning) {
      await stopContainer().catch(() => {});
    }
    await api.logout();
  });

  // ── Initial status check ──────────────────────────────────
  async function checkInitialStatus() {
    startBtn.disabled = true;
    try {
      // Refrescar datos del usuario
      const meData = await api.get('/api/me');
      user = meData.user;
      api.setUser(user);
      initUserUI();

      const data = await api.get('/api/container/status');
      if (data.status === 'running' && data.container_port) {
        setRunningUI(true, data.container_port);
        startStatsPolling();
        addLog('Contenedor ya activo, reconectado.', 'success');
      } else {
        setRunningUI(false);
        addLog('Listo para iniciar tu entorno Linux.', 'info');
      }
    } catch (err) {
      setStatus('stopped');
      addLog('Error al verificar estado. Reintenta más tarde.', 'error');
    } finally {
      startBtn.disabled = false;
    }
  }

  // ── Boot ──────────────────────────────────────────────────
  initUserUI();
  await checkInitialStatus();

  // Auto-stop al cerrar pestaña
  window.addEventListener('beforeunload', () => {
    if (isRunning) {
      navigator.sendBeacon('/api/container/stop', JSON.stringify({}));
    }
  });

})();
