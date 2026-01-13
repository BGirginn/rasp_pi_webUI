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
    let mouse = { x: null, y: null, radius: 250 };

    function resize() {
        canvas.width = canvas.offsetWidth;
        canvas.height = canvas.offsetHeight;
    }

    function handleMouseMove(e) {
        if (!opts.motion?.pointer) return;
        const rect = canvas.getBoundingClientRect();
        mouse.x = e.clientX - rect.left;
        mouse.y = e.clientY - rect.top;
    }

    function handleMouseLeave() {
        if (!opts.motion?.pointer) return;
        mouse.x = null;
        mouse.y = null;
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
        return { r: 250, g: 204, b: 21 }; // Default Gold
    }

    function animate() {
        if (!isRunning) return;

        ctx.clearRect(0, 0, canvas.width, canvas.height);

        const color = parseColor(particleColor);
        const rgb = `${color.r}, ${color.g}, ${color.b}`;

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
            ctx.fillStyle = `rgba(${rgb}, 0.8)`;
            ctx.fill();
        });

        // Draw connections with thick lines
        // Also connect to mouse
        const allParticles = [...particles];
        if (mouse.x != null) {
            allParticles.push({ x: mouse.x, y: mouse.y, radius: 0, isMouse: true });
        }

        for (let i = 0; i < allParticles.length; i++) {
            // Optimization: Only check connections for actual particles against others
            // For mouse (last item), we check against all previous
            const p1 = allParticles[i];

            for (let j = i + 1; j < allParticles.length; j++) {
                const p2 = allParticles[j];
                const dx = p1.x - p2.x;
                const dy = p1.y - p2.y;
                const distance = Math.sqrt(dx * dx + dy * dy);

                // Mouse interaction distance or regular connection distance
                const maxDist = (p1.isMouse || p2.isMouse) ? mouse.radius : connectionDistance;

                if (distance < maxDist) {
                    const opacity = (1 - distance / maxDist) * 0.6;
                    ctx.beginPath();
                    ctx.moveTo(p1.x, p1.y);
                    ctx.lineTo(p2.x, p2.y);
                    ctx.strokeStyle = `rgba(${rgb}, ${opacity})`;
                    ctx.lineWidth = 2; // Keep thick lines
                    ctx.stroke();
                }
            }
        }

        animationId = requestAnimationFrame(animate);
    }

    function start() {
        if (isRunning) return;
        isRunning = true;

        window.addEventListener('resize', debouncedResize);
        if (opts.motion?.pointer) {
            window.addEventListener('mousemove', handleMouseMove);
            window.addEventListener('mouseleave', handleMouseLeave);
        }

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
        window.removeEventListener('resize', debouncedResize);
        window.removeEventListener('mousemove', handleMouseMove);
        window.removeEventListener('mouseleave', handleMouseLeave);
    }

    const debouncedResize = debounce(() => {
        resize();
        init();
    }, 200);

    // Initial setup handled by start() to ensure listeners are clean
    return { start, stop, resize: debouncedResize };
}

export default initLuxuryNetwork;
