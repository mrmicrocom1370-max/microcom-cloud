from fastapi import FastAPI, HTTPException, Body, Response, Cookie
from fastapi.responses import HTMLResponse
import sqlite3
from datetime import datetime
from typing import Optional
import os

app = FastAPI(title="Microcom Enterprise Cloud Full")

# --- BLINDAJE DE RUTA PARA LA NUBE ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "pvmicrocom.db")

def inicializar_db():
    if not os.path.exists(DB_PATH): return
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("ALTER TABLE ventas_detalle ADD COLUMN id_venta INTEGER")
    except: pass 
    conn.commit(); conn.close()

inicializar_db()

def conectar():
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    return conn

@app.get("/", response_class=HTMLResponse)
def interfaz(user_role: Optional[str] = Cookie(None), user_name: Optional[str] = Cookie(None)):
    if not user_role:
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>Microcom - Login</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
            <style>
                body { background: #ff6600; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; font-family: sans-serif; }
                .login-card { background: white; padding: 40px; border-radius: 25px; box-shadow: 0 15px 35px rgba(0,0,0,0.3); width: 350px; text-align: center; }
                .btn-login { background: #000; color: white; font-weight: bold; border-radius: 12px; padding: 12px; width: 100%; border: none; margin-top: 10px; }
                input { width: 100%; padding: 12px; margin-bottom: 15px; border: 1px solid #ddd; border-radius: 12px; text-align: center; font-size: 16px; }
            </style>
        </head>
        <body>
            <div class="login-card">
                <h2 style="font-weight: 800; color: #333;">MICROCOM INK</h2>
                <input type="text" id="usuario" placeholder="Usuario">
                <input type="password" id="pin" placeholder="PIN">
                <button class="btn-login" onclick="ejecutarLogin()">ENTRAR</button>
            </div>
            <script>
                async function ejecutarLogin(){
                    const u = document.getElementById('usuario').value;
                    const p = document.getElementById('pin').value;
                    const res = await fetch('/login', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({u, p}) });
                    if(res.ok) location.reload(); else alert('Acceso denegado');
                }
            </script>
        </body>
        </html>
        """
    
    admin_style = "flex" if user_role == "admin" else "none"
    
    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Microcom Pro Cloud</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css">
        <script src="https://unpkg.com/html5-qrcode"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
        <style>
            body {{ background: #f4f7f6; font-family: 'Segoe UI', sans-serif; padding-bottom: 180px; }}
            .header-pro {{ background: #ff6600; color: white; padding: 15px; font-weight: bold; position: sticky; top: 0; z-index: 1000; }}
            .nav-buttons {{ background: white; display: flex; justify-content: space-around; padding: 10px; border-bottom: 2px solid #ff6600; margin-bottom: 15px; overflow-x: auto; }}
            .nav-btn {{ border: none; background: none; color: #666; font-weight: bold; font-size: 0.65rem; display: flex; flex-direction: column; align-items: center; min-width: 75px; }}
            .nav-btn.active {{ color: #ff6600; }}
            .nav-btn i {{ font-size: 1.4rem; }}
            .card-pro {{ border-radius: 15px; padding: 15px; background: white; margin-bottom: 10px; border: none; box-shadow: 0 4px 10px rgba(0,0,0,0.05); }}
            .precio-txt {{ color: #e65100; font-weight: 800; font-size: 1.2rem; }}
            .stock-badge {{ font-size: 0.85rem; background: #fff3e0; color: #e65100; border: 1px solid #ffcc80; padding: 2px 10px; border-radius: 8px; font-weight: 700; }}
            .footer-cobro {{ position: fixed; bottom: 0; width: 100%; background: white; padding: 15px; border-top: 4px solid #ff6600; z-index: 1000; box-shadow: 0 -5px 20px rgba(0,0,0,0.1); }}
            .admin-only {{ display: {admin_style} !important; }}
            .btn-del {{ color: #dc3545; border: none; background: none; font-size: 1.3rem; padding: 0; }}
            
            /* --- GUÍA VISUAL ESCÁNER HD --- */
            .scanner-wrapper {{ position: relative; width: 100%; max-width: 450px; margin: 0 auto 15px auto; display: none; overflow: hidden; border-radius: 20px; border: 4px solid #000; }}
            #reader {{ width: 100%; background: #000; }}
            .scanner-overlay {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; z-index: 5; box-shadow: inset 0 0 100px rgba(0,0,0,0.8); }}
            .scanner-laser {{ position: absolute; top: 50%; left: 10%; width: 80%; height: 3px; background: #ff0000; box-shadow: 0 0 15px #ff0000; z-index: 10; animation: laserMove 2s infinite ease-in-out; display: none; }}
            
            @keyframes laserMove {{
                0% {{ top: 30%; }}
                50% {{ top: 70%; }}
                100% {{ top: 30%; }}
            }}
            
            #modalTemporal, #modalTicket, #modalDetalle {{ position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.85); display: none; justify-content: center; align-items: center; z-index: 3000; }}
            .box-white {{ background: white; padding: 25px; border-radius: 20px; width: 90%; max-width: 380px; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="header-pro d-flex justify-content-between align-items-center px-3">
            <div>MICROCOM INK - {user_name}</div>
            <button class="btn btn-sm btn-outline-light" onclick="cerrarSesion()">Salir</button>
        </div>

        <div class="nav-buttons shadow-sm">
            <button class="nav-btn active" id="btn-venta" onclick="switchTab('venta')"><i class="bi bi-cart-plus"></i>VENTA</button>
            <button class="nav-btn" id="btn-consultas" onclick="switchTab('consultas')"><i class="bi bi-search"></i>STOCK</button>
            <button class="nav-btn" id="btn-historial" onclick="switchTab('historial')"><i class="bi bi-clock-history"></i>NOTAS</button>
            <button class="nav-btn admin-only" id="btn-reportes" onclick="switchTab('reportes')"><i class="bi bi-bar-chart-line"></i>CAJA</button>
            <button class="nav-btn text-danger d-none" id="btn-sync" onclick="sincronizarOffline()"><i class="bi bi-cloud-arrow-up-fill"></i>SYNC</button>
        </div>
        
        <div class="container">
            <div class="scanner-wrapper" id="scanner-container">
                <div id="reader"></div>
                <div class="scanner-overlay"></div>
                <div class="scanner-laser" id="laser-line"></div>
            </div>
            <button id="stop-scan" class="btn btn-danger w-100 mb-3" style="display:none" onclick="detenerEscaneo()">Cerrar Cámara</button>

            <div id="tab-venta">
                <div class="input-group mb-3 shadow-sm">
                    <input type="text" id="bus-v" class="form-control" placeholder="Escanear o buscar..." onkeyup="ejecutarBusqueda(this.value, 'res-v', 'venta')">
                    <button class="btn btn-dark" onclick="iniciarEscaneo('bus-v', 'res-v', 'venta')"><i class="bi bi-camera"></i></button>
                    <button class="btn btn-warning fw-bold" onclick="abrirTemporal()"><b>+</b></button>
                </div>
                <div id="res-v"></div>
                <div id="carrito-seccion" style="display:none;" class="mt-4"><div id="items-carrito"></div></div>
            </div>

            <div id="tab-historial" style="display:none;"><div id="lista-historial"></div></div>
            <div id="tab-consultas" style="display:none;"><div class="input-group mb-3 shadow-sm"><input type="text" id="bus-c" class="form-control" placeholder="Stock..." onkeyup="ejecutarBusqueda(this.value, 'res-c', 'consulta')"><button class="btn btn-dark" onclick="iniciarEscaneo('bus-c', 'res-c', 'consulta')"><i class="bi bi-camera"></i></button></div><div id="res-c"></div></div>
            <div id="tab-reportes" style="display:none;"><div class="card-pro text-center shadow-sm"><div class="text-muted fw-bold">VENTAS HOY</div><h1 class="text-success fw-bold m-0" id="rep-total">$0.00</h1><div class="badge bg-dark mt-2" id="rep-conteo">0 Ventas</div></div></div>
        </div>

        <div id="modalTemporal"><div class="box-white shadow-lg"><h5>SERVICIO ESPECIAL</h5><input type="text" id="temp-desc" class="form-control mb-2" placeholder="Descripción"><input type="number" id="temp-pre" class="form-control mb-3" placeholder="Precio ($)"><button class="btn btn-dark w-100 fw-bold" onclick="agregarTemporal()">AÑADIR</button><button class="btn btn-link btn-sm text-muted mt-2" onclick="cerrarTemporal()">Cancelar</button></div></div>
        <div id="modalTicket"><div class="box-white shadow-lg"><h5>ÉXITO</h5><div id="qrcode" class="d-flex justify-content-center my-3"></div><h4 class="text-success fw-bold" id="ticket-total"></h4><button class="btn btn-dark w-100 mt-2 fw-bold" onclick="location.reload()">NUEVA VENTA (ESC)</button></div></div>
        <div id="modalDetalle"><div class="box-white"><h5>DETALLE</h5><hr><div id="cont-detalle" class="text-start mb-3 small"></div><button class="btn btn-dark w-100" onclick="document.getElementById('modalDetalle').style.display='none'">Cerrar</button></div></div>

        <div id="footer-seccion" class="footer-cobro" style="display:none;">
            <div class="row g-2 px-2 align-items-center">
                <div class="col-6">PAGA CON:<input type="number" id="pago-cliente" class="form-control fw-bold border-2 border-warning" onkeyup="calcularCambio()"></div>
                <div class="col-6 text-end">CAMBIO:<h2 class="text-danger fw-bold m-0" id="cambio-cliente">$0.00</h2></div>
                <div class="col-12 mt-2"><div class="d-flex justify-content-between mb-1"><span class="fw-bold text-secondary">TOTAL: <span id="total-v" class="text-dark"></span></span><button class="btn btn-link btn-sm text-danger fw-bold p-0 text-decoration-none" onclick="cancelarVenta()">CANCELAR VENTA</button></div><button id="btn-cobrar" class="btn btn-success btn-lg w-100 fw-bold py-2 shadow" onclick="confirmarCobro()">REGISTRAR VENTA</button></div>
            </div>
        </div>

        <script>
            let carrito = []; let totalActual = 0; let scanner; let qrcodeGen = new QRCode(document.getElementById("qrcode"), {{ width: 200, height: 200 }});
            window.onload = () => {{ document.getElementById('bus-v').focus(); revisarVentasPendientes(); }};

            async function iniciarEscaneo(id, res, modo) {{
                document.getElementById('scanner-container').style.display = 'block'; 
                document.getElementById('stop-scan').style.display = 'block';
                document.getElementById('laser-line').style.display = 'block';
                scanner = new Html5Qrcode("reader");
                const config = {{ fps: 30, qrbox: {{ width: 300, height: 180 }}, aspectRatio: 1.0, videoConstraints: {{ facingMode: "environment", width: {{ ideal: 1280 }}, height: {{ ideal: 720 }} }} }};
                scanner.start({{ facingMode: "environment" }}, config, (text) => {{ document.getElementById(id).value = text; ejecutarBusqueda(text, res, modo); detenerEscaneo(); }}, () => {{}}).catch(err => console.log(err));
            }}

            function detenerEscaneo() {{ if (scanner) scanner.stop().then(() => {{ document.getElementById('scanner-container').style.display = 'none'; document.getElementById('stop-scan').style.display = 'none'; document.getElementById('laser-line').style.display = 'none'; }}); }}

            function switchTab(tab){{
                if (carrito.length > 0 && tab !== 'venta') {{ alert("⚠️ Venta activa. Debes Cobrar o Cancelar."); return; }}
                detenerEscaneo();
                ['bus-v', 'bus-c'].forEach(id => {{ if(document.getElementById(id)) document.getElementById(id).value = ''; }});
                ['res-v', 'res-c'].forEach(id => {{ if(document.getElementById(id)) document.getElementById(id).innerHTML = ''; }});
                ['venta', 'consultas', 'historial', 'reportes'].forEach(t => {{ if(document.getElementById('tab-' + t)) document.getElementById('tab-' + t).style.display = 'none'; }});
                document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
                document.getElementById('tab-' + tab).style.display = 'block';
                document.getElementById('btn-' + tab).classList.add('active');
                if(tab === 'reportes') cargarReportes();
                if(tab === 'historial') cargarHistorial();
            }}

            async function ejecutarBusqueda(q, target, modo){{
                const inputID = (modo === 'venta') ? 'bus-v' : 'bus-c';
                const contenedor = document.getElementById(target);
                if(!q || q.trim().length === 0) {{ contenedor.innerHTML = ''; return; }}
                const res = await fetch('/buscar?q=' + q); const productos = await res.json();
                contenedor.innerHTML = '';
                if (productos.length === 0) {{ contenedor.innerHTML = '<div class="alert-notfound text-center p-3 fw-bold text-danger">NO REGISTRADO</div>'; document.getElementById(inputID).value = ''; return; }}
                productos.forEach(p => {{
                    // !!! BLINDAJE DE PRECIOS: Busca P Mayúscula o p minúscula !!!
                    const pReal = parseFloat(p.Precio || p.precio || 0);
                    const sReal = p.Existencia !== undefined ? p.Existencia : (p.existencia !== undefined ? p.existencia : 0);
                    let accion = (modo === 'venta') ? `<button class="btn btn-dark fw-bold" onclick="agregarAlCarrito('${{p.CodigoProducto}}','${{p.Descripcion}}',${{pReal}})">Añadir</button>` : '';
                    contenedor.innerHTML += `<div class="card-pro d-flex justify-content-between align-items-center"><div><div class="fw-bold text-dark text-uppercase">${{p.Descripcion}}</div><div><span class="precio-txt">$${{pReal.toFixed(2)}}</span> <span class="stock-badge">Stock: ${{sReal}}</span></div></div>${{accion}}</div>`;
                }});
            }}

            function agregarAlCarrito(cod, desc, pre){{
                const ex = carrito.find(i => i.cod === cod);
                if(ex) ex.cant++; else carrito.push({{cod, desc, pre, cant: 1}});
                document.getElementById('bus-v').value = ''; document.getElementById('res-v').innerHTML = ''; actualizarVistaCarrito();
            }}

            function eliminarDelCarrito(index){{ carrito.splice(index, 1); actualizarVistaCarrito(); }}
            function cancelarVenta() {{ if(confirm("¿Cancelar?")) {{ carrito=[]; actualizarVistaCarrito(); }} }}

            function actualizarVistaCarrito(){{
                const div = document.getElementById('items-carrito'); const footer = document.getElementById('footer-seccion');
                if(carrito.length === 0) {{ document.getElementById('carrito-seccion').style.display = 'none'; footer.style.display = 'none'; return; }}
                document.getElementById('carrito-seccion').style.display = 'block'; footer.style.display = 'block';
                div.innerHTML = ''; totalActual = 0;
                carrito.forEach((i, idx) => {{
                    totalActual += i.pre * i.cant;
                    div.innerHTML += `<div class="card-pro d-flex justify-content-between align-items-center py-2"><div><div class="fw-bold text-uppercase">${{i.desc}} (x${{i.cant}})</div><div class="text-success fw-bold">$${{(i.pre*i.cant).toFixed(2)}}</div></div><button class="btn-del" onclick="eliminarDelCarrito(${{idx}})"><i class="bi bi-trash3-fill"></i></button></div>`;
                }});
                document.getElementById('total-v').innerText = '$' + totalActual.toFixed(2); calcularCambio();
            }}

            function calcularCambio() {{
                const p = parseFloat(document.getElementById('pago-cliente').value) || 0;
                const c = p - totalActual;
                document.getElementById('cambio-cliente').innerText = '$' + (c > 0 ? c.toFixed(2) : '0.00');
                document.getElementById('btn-cobrar').disabled = (p < totalActual);
            }}

            async function confirmarCobro(){{
                const p = parseFloat(document.getElementById('pago-cliente').value);
                const venta = {{ items: carrito, pago: p, cambio: p - totalActual, fecha_local: new Date().toLocaleString() }};
                
                try {{
                    const res = await fetch('/vender', {{ method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify(venta) }});
                    if(res.ok) {{ document.getElementById('modalTicket').style.display = 'flex'; }}
                    else {{ throw new Error("Error Servidor"); }}
                }} catch (err) {{
                    let pendientes = JSON.parse(localStorage.getItem('pendientes') || '[]');
                    pendientes.push(venta);
                    localStorage.setItem('pendientes', JSON.stringify(pendientes));
                    alert("⚠️ GUARDADO EN CELULAR. Cuando haya red dale al botón SYNC.");
                    document.getElementById('modalTicket').style.display = 'flex';
                    revisarVentasPendientes();
                }}
            }}

            function revisarVentasPendientes() {{
                let p = JSON.parse(localStorage.getItem('pendientes') || '[]');
                if(p.length > 0) document.getElementById('btn-sync').classList.remove('d-none');
                else document.getElementById('btn-sync').classList.add('d-none');
            }}

            async function sincronizarOffline() {{
                let p = JSON.parse(localStorage.getItem('pendientes') || '[]');
                for(let v of p) {{
                    await fetch('/vender', {{ method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify(v) }});
                }}
                localStorage.removeItem('pendientes'); revisarVentasPendientes(); alert("✅ Sincronizado");
            }}

            async function cargarHistorial() {{
                const res = await fetch('/historial'); const ventas = await res.json();
                const lista = document.getElementById('lista-historial'); lista.innerHTML = '';
                ventas.forEach(v => {{ lista.innerHTML += `<div class="card-pro d-flex justify-content-between align-items-center" onclick="verDetalleNota(${{v.id}})"><div><div class="fw-bold">Nota #${{v.id}} - $${{parseFloat(v.total).toFixed(2)}}</div><div class="articulos-resumen">${{v.articulos || 'Detalle...'}}</div><small class="text-muted">${{v.fecha}}</small></div><i class="bi bi-chevron-right text-muted"></i></div>`; }});
            }}

            async function verDetalleNota(id) {{
                const res = await fetch('/detalle-venta/' + id); const items = await res.json();
                const cont = document.getElementById('cont-detalle'); cont.innerHTML = '';
                items.forEach(i => {{ cont.innerHTML += `<div class="d-flex justify-content-between border-bottom py-1"><span>${{i.descripcion}} (x${{i.cantidad}})</span><b>$${{parseFloat(i.total_cobrado).toFixed(2)}}</b></div>`; }});
                document.getElementById('modalDetalle').style.display = 'flex';
            }}

            function cerrarTicket() {{ location.reload(); }}
            async function cargarReportes(){{ const res = await fetch('/reporte-hoy'); const d = await res.json(); document.getElementById('rep-total').innerText = '$' + d.total_dia.toFixed(2); document.getElementById('rep-conteo').innerText = d.conteo + ' Ventas'; }}
            async function cerrarSesion(){{ await fetch('/logout', {{method: 'POST'}}); location.reload(); }}
        </script>
    </body>
    </html>
    """

@app.post("/vender")
def vender(payload: dict = Body(...), user_role: Optional[str] = Cookie(None)):
    if not user_role: raise HTTPException(status_code=401)
    items = payload['items']; total_v = sum(item['pre'] * item['cant'] for item in items)
    ahora = datetime.now(); f = ahora.strftime("%Y-%m-%d %H:%M:%S")
    conn = conectar(); cur = conn.cursor()
    try:
        cur.execute("INSERT INTO ventas (fecha, total) VALUES (?, ?)", (f, total_v))
        v_id = cur.lastrowid
        for i in items:
            cur.execute("INSERT INTO ventas_detalle (id_venta, fecha, hora, codigo, descripcion, cantidad, total_cobrado) VALUES (?, ?, ?, ?, ?, ?, ?)", (v_id, ahora.strftime("%Y-%m-%d"), ahora.strftime("%H:%M:%S"), i['cod'], i['desc'], i['cant'], i['pre'] * i['cant']))
        conn.commit(); return {"ok": True}
    finally: conn.close()

@app.get("/buscar")
def buscar(q: str, user_role: Optional[str] = Cookie(None)):
    if not user_role: raise HTTPException(status_code=401)
    conn = conectar()
    res = conn.execute("SELECT CodigoProducto, Descripcion, Precio, Existencia FROM productos WHERE Descripcion LIKE ? OR CodigoProducto = ?", (f'%{q}%', q)).fetchall()
    conn.close(); return [dict(row) for row in res]

@app.get("/historial")
def historial():
    conn = conectar()
    res = conn.execute("SELECT v.id, v.fecha, v.total, (SELECT GROUP_CONCAT(descripcion, ', ') FROM ventas_detalle WHERE id_venta = v.id) as articulos FROM ventas v ORDER BY v.id DESC LIMIT 15").fetchall()
    conn.close(); return [dict(row) for row in res]

@app.get("/detalle-venta/{venta_id}")
def detalle_venta(venta_id: int):
    conn = conectar(); res = conn.execute("SELECT descripcion, cantidad, total_cobrado FROM ventas_detalle WHERE id_venta = ?", (venta_id,)).fetchall(); conn.close()
    return [dict(row) for row in res]

@app.get("/reporte-hoy")
def reporte_hoy(user_role: Optional[str] = Cookie(None)):
    if user_role != "admin": raise HTTPException(status_code=403)
    f = datetime.now().strftime("%Y-%m-%d")
    conn = conectar()
    res = conn.execute("SELECT SUM(total) as total, COUNT(*) as conteo FROM ventas WHERE fecha LIKE ?", (f'{f}%',)).fetchone()
    conn.close(); return {"total_dia": res['total'] or 0, "conteo": res['conteo']}

@app.post("/login")
def login(response: Response, data: dict = Body(...)):
    if data['u'] == "admin" and data['p'] == "1234":
        response.set_cookie(key="user_role", value="admin", httponly=True); return {"ok": True}
    raise HTTPException(status_code=401)

@app.post("/logout")
def logout(response: Response):
    response.delete_cookie("user_role"); return {"ok": True}