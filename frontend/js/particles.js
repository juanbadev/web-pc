/* Partículas flotantes para la landing page */
(function () {
  const canvas = document.getElementById('particles');
  if (!canvas) return;
  const ctx    = canvas.getContext('2d');
  let W, H, particles = [];

  function resize() {
    W = canvas.width  = window.innerWidth;
    H = canvas.height = window.innerHeight;
  }

  function rand(a, b) { return a + Math.random() * (b - a); }

  class Particle {
    constructor() { this.reset(); }
    reset() {
      this.x  = rand(0, W);
      this.y  = rand(0, H);
      this.r  = rand(1, 2.5);
      this.vx = rand(-.3, .3);
      this.vy = rand(-.5, -.1);
      this.a  = rand(.2, .7);
    }
    update() {
      this.x += this.vx;
      this.y += this.vy;
      if (this.y < -5 || this.x < -5 || this.x > W + 5) this.reset();
    }
    draw() {
      ctx.beginPath();
      ctx.arc(this.x, this.y, this.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(0, 212, 170, ${this.a})`;
      ctx.fill();
    }
  }

  function init() {
    resize();
    particles = Array.from({ length: 80 }, () => new Particle());
    loop();
  }

  function loop() {
    ctx.clearRect(0, 0, W, H);
    particles.forEach(p => { p.update(); p.draw(); });

    // Líneas entre partículas cercanas
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const dx = particles[i].x - particles[j].x;
        const dy = particles[i].y - particles[j].y;
        const d  = Math.sqrt(dx * dx + dy * dy);
        if (d < 80) {
          ctx.beginPath();
          ctx.moveTo(particles[i].x, particles[i].y);
          ctx.lineTo(particles[j].x, particles[j].y);
          ctx.strokeStyle = `rgba(0, 212, 170, ${(1 - d / 80) * 0.15})`;
          ctx.lineWidth = .5;
          ctx.stroke();
        }
      }
    }

    requestAnimationFrame(loop);
  }

  window.addEventListener('resize', () => { resize(); });
  init();
})();
