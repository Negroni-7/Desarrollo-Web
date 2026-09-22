// ============================================
// VERIFICACIÓN DE EDAD
// ============================================
document.addEventListener('DOMContentLoaded', function() {
    const ageModal = new bootstrap.Modal(document.getElementById('ageModal'));
    ageModal.show();
});

function confirmarEdad() {
    const modal = bootstrap.Modal.getInstance(document.getElementById('ageModal'));
    modal.hide();
}

function rechazarEdad() {
    window.location.href = 'https://www.google.com';
}

// ============================================
// FILTROS
// ============================================
function filtrarVinos(tipo, btn) {
    // Filtrar tarjetas
    const tarjetas = document.querySelectorAll('.wine-card');
    tarjetas.forEach(tarjeta => {
        const tipoVino = tarjeta.getAttribute('data-tipo');
        if (tipo === 'todos' || tipoVino === tipo) {
            tarjeta.style.display = 'block';
        } else {
            tarjeta.style.display = 'none';
        }
    });

    // Actualizar botón activo
    document.querySelectorAll('.filter-btn').forEach(b => {
        b.classList.remove('active');
        b.classList.remove('btn-acento');
        b.classList.add('btn-outline-secondary');
    });
    btn.classList.add('active');
    btn.classList.remove('btn-outline-secondary');
    btn.classList.add('btn-acento');
}

// ============================================
// CARRITO
// ============================================
let carrito = JSON.parse(localStorage.getItem('carrito')) || [];

function agregarAlCarrito(btn) {
    const nombre = btn.getAttribute('data-nombre');
    const precio = parseInt(btn.getAttribute('data-precio'));
    const imagen = btn.getAttribute('data-imagen');

    // Verificar si ya está en el carrito
    const existente = carrito.find(item => item.nombre === nombre);
    if (existente) {
        existente.cantidad++;
    } else {
        carrito.push({ nombre, precio, imagen, cantidad: 1 });
    }

    guardarCarrito();
    actualizarCarrito();
    mostrarNotificacion(nombre);
}

function eliminarDelCarrito(nombre) {
    carrito = carrito.filter(item => item.nombre !== nombre);
    guardarCarrito();
    actualizarCarrito();
}

function cambiarCantidad(nombre, delta) {
    const item = carrito.find(item => item.nombre === nombre);
    if (item) {
        item.cantidad += delta;
        if (item.cantidad <= 0) {
            eliminarDelCarrito(nombre);
            return;
        }
    }
    guardarCarrito();
    actualizarCarrito();
}

function guardarCarrito() {
    localStorage.setItem('carrito', JSON.stringify(carrito));
}

function actualizarCarrito() {
    const count = carrito.reduce((sum, item) => sum + item.cantidad, 0);
    const total = carrito.reduce((sum, item) => sum + (item.precio * item.cantidad), 0);

    document.getElementById('cartCount').textContent = count;
    document.getElementById('cartSubtotal').textContent = '$' + total.toLocaleString('es-CL');
    document.getElementById('cartTotal').textContent = '$' + total.toLocaleString('es-CL');

    const container = document.getElementById('cartItems');
    if (carrito.length === 0) {
        container.innerHTML = `
            <div class="text-center py-5">
                <i class="bi bi-cart-x display-1 text-muted"></i>
                <h5 class="mt-3 text-muted">Tu carrito está vacío</h5>
                <p class="text-muted">Explora nuestro catálogo para encontrar vinos increíbles</p>
            </div>
        `;
    } else {
        container.innerHTML = carrito.map(item => `
            <div class="d-flex gap-3 mb-3 p-2 border-bottom">
                <img src="${item.imagen}" alt="${item.nombre}" style="width: 60px; height: 60px; object-fit: cover; border-radius: 8px;">
                <div class="flex-grow-1">
                    <h6 class="mb-1" style="font-size: 0.9rem;">${item.nombre}</h6>
                    <p class="mb-1 fw-bold" style="color: var(--color-acento);">$${item.precio.toLocaleString('es-CL')}</p>
                    <div class="d-flex align-items-center gap-2">
                        <button class="btn btn-sm btn-outline-secondary" style="width: 28px; height: 28px;" onclick="cambiarCantidad('${item.nombre}', -1)">-</button>
                        <span class="fw-bold">${item.cantidad}</span>
                        <button class="btn btn-sm btn-outline-secondary" style="width: 28px; height: 28px;" onclick="cambiarCantidad('${item.nombre}', 1)">+</button>
                        <button class="btn btn-sm text-danger ms-auto" onclick="eliminarDelCarrito('${item.nombre}')"><i class="bi bi-trash"></i></button>
                    </div>
                </div>
            </div>
        `).join('');
    }
}

function mostrarNotificacion(nombre) {
    // Crear notificación
    const notif = document.createElement('div');
    notif.className = 'notificacion';
    notif.innerHTML = `<i class="bi bi-check-circle-fill me-2"></i>${nombre} agregado al carrito`;
    document.body.appendChild(notif);

    setTimeout(() => notif.classList.add('show'), 10);
    setTimeout(() => {
        notif.classList.remove('show');
        setTimeout(() => notif.remove(), 300);
    }, 2000);
}

// ============================================
// CARRITO SIDEBAR
// ============================================
function abrirCarrito() {
    document.getElementById('cartSidebar').classList.add('open');
    document.getElementById('cartOverlay').classList.add('show');
    document.body.style.overflow = 'hidden';
    actualizarCarrito();
}

function cerrarCarrito() {
    document.getElementById('cartSidebar').classList.remove('open');
    document.getElementById('cartOverlay').classList.remove('show');
    document.body.style.overflow = '';
}

// ============================================
// MODAL USUARIO
// ============================================
function abrirUsuario() {
    const modal = new bootstrap.Modal(document.getElementById('userModal'));
    modal.show();
}

function mostrarTab(tab) {
    const tabs = document.querySelectorAll('#userModal .nav-link');
    tabs.forEach(t => t.classList.remove('active'));

    if (tab === 'login') {
        tabs[0].classList.add('active');
        document.getElementById('tabLogin').style.display = 'block';
        document.getElementById('tabRegister').style.display = 'none';
    } else {
        tabs[1].classList.add('active');
        document.getElementById('tabLogin').style.display = 'none';
        document.getElementById('tabRegister').style.display = 'block';
    }
}

// Cargar carrito al iniciar
document.addEventListener('DOMContentLoaded', function() {
    actualizarCarrito();
});

// ============================================
// SCROLL A RESERVA
// ============================================
function scrollAReserva() {
    const formulario = document.getElementById('formulario-reserva');
    if (formulario) {
        const offset = 80;
        const top = formulario.getBoundingClientRect().top + window.pageYOffset - offset;
        window.scrollTo({ top: top, behavior: 'smooth' });
    }
}

// ============================================
// CARRUSEL
// ============================================
let carouselPosition = 0;

function moverCarrusel(direccion) {
    const track = document.getElementById('carouselTrack');
    const cards = track.querySelectorAll('.carousel-card');
    const cardWidth = cards[0].offsetWidth + 20; // ancho + gap
    const visibleCards = Math.floor(track.parentElement.offsetWidth / cardWidth);
    const maxPosition = cards.length - visibleCards;

    carouselPosition += direccion;

    if (carouselPosition < 0) carouselPosition = 0;
    if (carouselPosition > maxPosition) carouselPosition = maxPosition;

    track.style.transform = `translateX(-${carouselPosition * cardWidth}px)`;
}
