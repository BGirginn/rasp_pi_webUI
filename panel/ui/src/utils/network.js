/* network.js - Particle System Animation */

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

export function initLuxuryNetwork(opts) {
    const canvas = opts.canvas;
    const ctx = canvas.getContext('2d');

    const particleColor = opts.particleColor || 'rgb(250, 204, 21)';
    const particleCount = opts.particleCount || 150;
    const connectionDistance = opts.connectionDistance || 180;

    let particles = [];
    let animationId = null;
    let isRunning = false;

    function resize() {
        canvas.width = canvas.offsetWidth;
        canvas.height = canvas.offsetHeight;
    }

    function init() {
        particles = [];
        for (let i = 0; i < particleCount; i++) {
            particles.push({
                x: Math.random() * canvas.width,
                y: Math.random() * canvas.height,
                vx: (Math.random() - 0.5) * 0.5,
                vy: (Math.random() - 0.5) * 0.5,
                radius: Math.random() * 2 + 1 // Simple particles (1-3px)
            });
        }
    }

    function parseColor(color) {
        const match = color.match(/\d+/g);
        if (match && match.length >= 3) {
            return { r: parseInt(match[0]), g: parseInt(match[1]), b: parseInt(match[2]) };
        }
        return { r: 250, g: 204, b: 21 };
    }

    function animate() {
        if (!isRunning) return;

        ctx.clearRect(0, 0, canvas.width, canvas.height);

        const color = parseColor(particleColor);

        // Update and draw particles (simple style)
        particles.forEach(particle => {
            particle.x += particle.vx;
            particle.y += particle.vy;

            // Bounce off edges
            if (particle.x < 0 || particle.x > canvas.width) particle.vx *= -1;
            if (particle.y < 0 || particle.y > canvas.height) particle.vy *= -1;

            // Draw simple particle
            ctx.beginPath();
            ctx.arc(particle.x, particle.y, particle.radius, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(${color.r}, ${color.g}, ${color.b}, 0.8)`;
            ctx.fill();
        });

        // Draw connections with thick lines
        for (let i = 0; i < particles.length; i++) {
            for (let j = i + 1; j < particles.length; j++) {
                const dx = particles[i].x - particles[j].x;
                const dy = particles[i].y - particles[j].y;
                const distance = Math.sqrt(dx * dx + dy * dy);

                if (distance < connectionDistance) {
                    const opacity = (1 - distance / connectionDistance) * 0.6;
                    ctx.beginPath();
                    ctx.moveTo(particles[i].x, particles[i].y);
                    ctx.lineTo(particles[j].x, particles[j].y);
                    ctx.strokeStyle = `rgba(${color.r}, ${color.g}, ${color.b}, ${opacity})`;
                    ctx.lineWidth = 2;
                    ctx.stroke();
                }
            }
        }

        animationId = requestAnimationFrame(animate);
    }

    function start() {
        if (isRunning) return;
        isRunning = true;
        resize();
        init();
        animate();
    }

    function stop() {
        isRunning = false;
        if (animationId) {
            cancelAnimationFrame(animationId);
            animationId = null;
        }
    }

    const debouncedResize = debounce(() => {
        resize();
        init();
    }, 200);

    window.addEventListener('resize', debouncedResize);

    resize();
    init();

    return { start, stop, resize: debouncedResize };
}

export default initLuxuryNetwork;
