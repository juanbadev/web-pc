/**
 * LinuxCloud - API Client
 * Módulo global `api` para toda la aplicación
 */
const api = (() => {
  const BASE = '';  // mismo origen

  // ── Storage ──────────────────────────────────────────
  const getToken = () => localStorage.getItem('lc_token');
  const setToken = (t) => localStorage.setItem('lc_token', t);
  const removeToken = () => localStorage.removeItem('lc_token');

  const getUser = () => {
    try { return JSON.parse(localStorage.getItem('lc_user') || 'null'); }
    catch { return null; }
  };
  const setUser = (u) => localStorage.setItem('lc_user', JSON.stringify(u));
  const removeUser = () => localStorage.removeItem('lc_user');

  // ── HTTP helpers ──────────────────────────────────────
  async function request(method, path, body = null) {
    const headers = { 'Content-Type': 'application/json' };
    const token = getToken();
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const opts = { method, headers };
    if (body) opts.body = JSON.stringify(body);

    let res;
    try {
      res = await fetch(BASE + path, opts);
    } catch (e) {
      throw new Error('No se pudo conectar con el servidor. Verifica tu conexión.');
    }

    let data;
    try { data = await res.json(); }
    catch { data = {}; }

    if (!res.ok) {
      // Si token expirado, limpiar sesión
      if (res.status === 401) {
        removeToken();
        removeUser();
        if (!window.location.pathname.includes('login') &&
            !window.location.pathname.includes('register') &&
            window.location.pathname !== '/') {
          window.location.href = '/login.html';
        }
      }
      throw new Error(data.error || data.message || `Error ${res.status}`);
    }

    return data;
  }

  const get  = (path)       => request('GET', path);
  const post = (path, body) => request('POST', path, body);

  // ── Auth helpers ──────────────────────────────────────
  function isLoggedIn() {
    return !!getToken();
  }

  async function logout() {
    try {
      await post('/api/logout', {});
    } catch (_) {
      // Continuar aunque falle la llamada
    } finally {
      removeToken();
      removeUser();
      window.location.href = '/login.html';
    }
  }

  return { get, post, getToken, setToken, removeToken, getUser, setUser, removeUser, isLoggedIn, logout };
})();
