/* Efecto de typewriter para la terminal demo de la landing */
(function () {
  const el = document.getElementById('demoTerm');
  if (!el) return;

  const lines = [
    { text: '$ whoami',                           color: '#00d4aa', delay: 400 },
    { text: 'linuxuser',                           color: '#a8ff78', delay: 200 },
    { text: '$ uname -a',                          color: '#00d4aa', delay: 600 },
    { text: 'Linux cloud 5.15.0 #1 SMP Ubuntu',   color: '#a8ff78', delay: 200 },
    { text: '$ ls -la',                            color: '#00d4aa', delay: 700 },
    { text: 'total 32\ndrwxr-xr-x  5 linuxuser linuxuser 4096 ...\n-rw-r--r--  1 linuxuser linuxuser  220 .bash_logout\n-rw-r--r--  1 linuxuser linuxuser 3526 .bashrc', color: '#a8ff78', delay: 200 },
    { text: '$ python3 --version',                 color: '#00d4aa', delay: 800 },
    { text: 'Python 3.10.12',                      color: '#a8ff78', delay: 200 },
    { text: '$ echo "Mi Linux en la nube 🚀"',     color: '#00d4aa', delay: 700 },
    { text: 'Mi Linux en la nube 🚀',              color: '#fbbf24', delay: 200 },
    { text: '$ _',                                 color: '#00d4aa', delay: 600 },
  ];

  let lineIdx = 0;
  let charIdx = 0;
  let currentDiv = null;

  function nextLine() {
    if (lineIdx >= lines.length) {
      // Reiniciar demo con fade
      setTimeout(() => {
        el.innerHTML = '';
        lineIdx = 0; charIdx = 0;
        scheduleNext();
      }, 3000);
      return;
    }

    const line = lines[lineIdx];
    // Pausa antes de escribir la línea
    setTimeout(() => typeLine(line), line.delay);
  }

  function typeLine(line) {
    const subLines = line.text.split('\n');
    typeSubLines(subLines, 0, line.color, () => {
      lineIdx++;
      nextLine();
    });
  }

  function typeSubLines(subs, idx, color, done) {
    if (idx >= subs.length) { done(); return; }

    currentDiv = document.createElement('div');
    currentDiv.style.color = color;
    el.appendChild(currentDiv);
    charIdx = 0;

    const text = subs[idx];
    const speed = text.startsWith('$') ? 60 : 20;

    function typeChar() {
      if (charIdx < text.length) {
        currentDiv.textContent += text[charIdx++];
        el.scrollTop = el.scrollHeight;
        setTimeout(typeChar, speed + Math.random() * 30);
      } else {
        typeSubLines(subs, idx + 1, color, done);
      }
    }
    typeChar();
  }

  function scheduleNext() { nextLine(); }
  scheduleNext();
})();
