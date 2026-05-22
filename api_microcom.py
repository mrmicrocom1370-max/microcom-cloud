import os
import urllib.request

# --- CONFIGURACIÓN DE CARPETAS ---
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "estaticos")
os.makedirs(os.path.join(STATIC_DIR, "fonts"), exist_ok=True)

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Empresas")
FOTOS_DIR = os.path.join(BASE_DIR, "fotos")
os.makedirs(FOTOS_DIR, exist_ok=True)

# --- FUNCIÓN DE DESCARGA INTELIGENTE ---
def descargar_estaticos():
    archivos = {
        "bootstrap.min.css": "https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css",
        # Corregí la URL para que apunte directamente al archivo .js
        "html5-qrcode.min.js": "https://unpkg.com/html5-qrcode/html5-qrcode.min.js",
        # Te agrego el JS de Bootstrap de regalo por si usas ventanas emergentes (modales)
        "bootstrap.bundle.min.js": "https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"
    }

    print("Verificando archivos estáticos locales...")
    
    for nombre_archivo, url in archivos.items():
        ruta_destino = os.path.join(STATIC_DIR, nombre_archivo)
        
        # Si el archivo NO existe en la carpeta, procede a descargarlo
        if not os.path.exists(ruta_destino):
            print(f"Descargando {nombre_archivo}...")
            try:
                urllib.request.urlretrieve(url, ruta_destino)
                print(f"✅ {nombre_archivo} descargado y guardado correctamente.")
            except Exception as e:
                print(f"❌ Error al descargar {nombre_archivo}: {e}")
        else:
            # Si ya existe, no pierde tiempo y lo avisa en la consola
            pass 
            # print(f"✔️ {nombre_archivo} ya existe. Todo en orden.")

# Ejecutamos la función al iniciar el script
descargar_estaticos()
import csv
import io
import json
import shutil
import random
import time
from datetime import datetime
from typing import Optional
import urllib.parse
import sqlite3

from fastapi import FastAPI, HTTPException, Body, Response, Cookie, File, UploadFile, BackgroundTasks, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pyngrok import ngrok
import uvicorn
from supabase import create_client, Client

# --- 1. CONEXIÓN A LA NUBE (SUPABASE) ---
SUPABASE_URL = "https://fudqwgemvvlimmmsfndn.supabase.co"
SUPABASE_KEY = "sb_publishable_0YRuQxWTT8n6Q5dOzeFN5g_gvG3AF3M"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI(title="Cloud POS - Híbrido Total Offline")

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "estaticos")
os.makedirs(os.path.join(STATIC_DIR, "fonts"), exist_ok=True)

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Empresas")
FOTOS_DIR = os.path.join(BASE_DIR, "fotos")
os.makedirs(FOTOS_DIR, exist_ok=True)

def descargar_estaticos():
    archivos = {
        "bootstrap.min.css": "https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css",
        "html5-qrcode.min.js": "https://unpkg.com/html5-qrcode",
        "qrcode.min.js": "https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js",
        "bootstrap-icons.css": "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css",
        "fonts/bootstrap-icons.woff2": "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/fonts/bootstrap-icons.woff2",
        "fonts/bootstrap-icons.woff": "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/fonts/bootstrap-icons.woff"
    }
    for nombre, url in archivos.items():
        ruta = os.path.join(STATIC_DIR, nombre)
        if not os.path.exists(ruta):
            try: urllib.request.urlretrieve(url, ruta)
            except: pass

descargar_estaticos()
app.mount("/estaticos", StaticFiles(directory=STATIC_DIR), name="estaticos")
app.mount("/fotos-locales", StaticFiles(directory=FOTOS_DIR), name="fotos-locales")

MASTER_DB = os.path.join(BASE_DIR, "cloud_master.db")

# --- ESTO ES PARA AGREGAR LA COLUMNA DE ALERTA UNA SOLA VEZ ---
def actualizar_base_de_datos():
    conn = sqlite3.connect(MASTER_DB)
    try:
        # Aquí le decimos al cuaderno: "Agrega la columna stock_minimo"
        conn.execute("ALTER TABLE productos ADD COLUMN stock_minimo INTEGER DEFAULT 5")
        conn.commit()
        print("✅ ¡Columna de Inventario Mínimo agregada con éxito!")
    except Exception as e:
        # Si ya existe, nos dará un error, pero no pasa nada, solo lo ignoramos
        print("La columna ya existía o hubo un detalle:", e)
    finally:
        conn.close()

# Ejecutamos la función para que haga el cambio en tu base de datos
actualizar_base_de_datos()

def init_master_db():
    conn = sqlite3.connect(MASTER_DB)
    conn.execute("CREATE TABLE IF NOT EXISTS super_usuarios (id INTEGER PRIMARY KEY, nombre TEXT, pin TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS empresas (id INTEGER PRIMARY KEY, nombre_comercial TEXT, db_alias TEXT, fecha_creacion TEXT)")
    try: conn.execute("ALTER TABLE empresas ADD COLUMN giro TEXT DEFAULT 'general'")
    except: pass
    conn.execute("CREATE TABLE IF NOT EXISTS buzon_salida (id INTEGER PRIMARY KEY AUTOINCREMENT, tabla TEXT, operacion TEXT, datos TEXT, col_filtro TEXT, val_filtro TEXT, empresa_id TEXT)")
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM super_usuarios")
    if cur.fetchone()[0] == 0:
        conn.execute("INSERT INTO super_usuarios (nombre, pin) VALUES ('CloudMaster', '9999')")
    conn.commit(); conn.close()

init_master_db()

def get_db_path(business_id: str): return os.path.join(BASE_DIR, f"pv_{business_id}.db")

def inicializar_db(ruta):
    conn = sqlite3.connect(ruta)
    conn.execute("CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY, nombre TEXT, pin TEXT, rol TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS productos (CodigoProducto TEXT PRIMARY KEY, Descripcion TEXT, Precio REAL, Existencia REAL)")
    conn.execute("CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, total REAL, cliente TEXT DEFAULT 'GENERAL', estado TEXT DEFAULT 'COMPLETADA', saldo_pendiente REAL DEFAULT 0)")
    conn.execute("CREATE TABLE IF NOT EXISTS ventas_detalle (id INTEGER PRIMARY KEY AUTOINCREMENT, id_venta INTEGER, fecha TEXT, hora TEXT, codigo TEXT, descripcion TEXT, cantidad REAL, total_cobrado REAL)")
    conn.execute("CREATE TABLE IF NOT EXISTS abonos (id INTEGER PRIMARY KEY AUTOINCREMENT, id_venta INTEGER, fecha TEXT, monto REAL)")
    conn.execute("CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, descripcion TEXT, monto REAL)")
    conn.execute("CREATE TABLE IF NOT EXISTS cotizaciones (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, total REAL, estado TEXT DEFAULT 'ACTIVA')")
    conn.execute("CREATE TABLE IF NOT EXISTS cotizaciones_detalle (id INTEGER PRIMARY KEY AUTOINCREMENT, id_cotizacion INTEGER, codigo TEXT, descripcion TEXT, cantidad REAL, precio REAL)")
    conn.execute("CREATE TABLE IF NOT EXISTS promociones (id INTEGER PRIMARY KEY AUTOINCREMENT, codigo_producto TEXT, cantidad_requerida INTEGER, precio_promocional REAL, fecha_inicio TEXT, fecha_fin TEXT, activa INTEGER DEFAULT 1)")
    conn.execute("CREATE TABLE IF NOT EXISTS configuracion (parametro TEXT PRIMARY KEY, valor TEXT)")
    
    parches = [
        "ALTER TABLE ventas_detalle ADD COLUMN id_venta INTEGER",
        "ALTER TABLE ventas ADD COLUMN cliente TEXT DEFAULT 'GENERAL'",
        "ALTER TABLE ventas ADD COLUMN estado TEXT DEFAULT 'COMPLETADA'",
        "ALTER TABLE ventas ADD COLUMN saldo_pendiente REAL DEFAULT 0",
        "ALTER TABLE productos ADD COLUMN FechaCaptura TEXT",
        "ALTER TABLE productos ADD COLUMN Marca TEXT",
        "ALTER TABLE productos ADD COLUMN Proveedor TEXT",
        "ALTER TABLE productos ADD COLUMN Almacen TEXT",
        "ALTER TABLE productos ADD COLUMN Costo REAL DEFAULT 0",
        "ALTER TABLE ventas_detalle ADD COLUMN metodo_pago TEXT DEFAULT 'EFECTIVO'",
        "ALTER TABLE ventas ADD COLUMN cajero TEXT DEFAULT 'SISTEMA'",
        "ALTER TABLE abonos ADD COLUMN cajero TEXT DEFAULT 'SISTEMA'",
        "ALTER TABLE abonos ADD COLUMN metodo TEXT DEFAULT 'EFECTIVO'",
        "ALTER TABLE gastos ADD COLUMN cajero TEXT DEFAULT 'SISTEMA'",
        "ALTER TABLE ventas ADD COLUMN estado_produccion TEXT DEFAULT 'ENTREGADO'",
        "CREATE TABLE IF NOT EXISTS clientes (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE, telefono TEXT, correo TEXT, fecha_registro TEXT)",
        "ALTER TABLE productos ADD COLUMN IVA REAL DEFAULT 0",
        "ALTER TABLE productos ADD COLUMN Unidad TEXT DEFAULT 'PZ'",
        "ALTER TABLE productos ADD COLUMN Categoria TEXT DEFAULT 'GENERAL'",
        "ALTER TABLE productos ADD COLUMN FechaEntrada TEXT",
        "ALTER TABLE productos ADD COLUMN Prov_WhatsApp TEXT",
        "ALTER TABLE productos ADD COLUMN Prov_Mail TEXT",
        "ALTER TABLE productos ADD COLUMN imagen TEXT",
        "ALTER TABLE productos ADD COLUMN Caducidad TEXT",
        "ALTER TABLE ventas ADD COLUMN link_archivo TEXT",
        "ALTER TABLE cotizaciones ADD COLUMN link_archivo TEXT",
        "ALTER TABLE clientes ADD COLUMN puntos REAL DEFAULT 0",
        "CREATE TABLE IF NOT EXISTS fondo_caja (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, monto REAL, cajero TEXT)",
        "ALTER TABLE productos ADD COLUMN Precio_2 REAL DEFAULT 0",
        "ALTER TABLE productos ADD COLUMN Cant_P2 REAL DEFAULT 0",
        "ALTER TABLE productos ADD COLUMN Precio_3 REAL DEFAULT 0",
        "ALTER TABLE productos ADD COLUMN Cant_P3 REAL DEFAULT 0",
        "ALTER TABLE productos ADD COLUMN Precio_Especial REAL DEFAULT 0"
    ]
    for parche in parches:
        try: conn.execute(parche)
        except: pass
    conn.commit(); conn.close()

def conectar(business_id: str):
    ruta = get_db_path(business_id); inicializar_db(ruta) 
    conn = sqlite3.connect(ruta); conn.row_factory = sqlite3.Row
    return conn

def sync_to_supabase(tabla: str, datos: dict):
    try:
        if tabla == "productos" and "CodigoProducto" not in datos and "codigo_producto" in datos: datos["CodigoProducto"] = datos.pop("codigo_producto")
        supabase.table(tabla).insert(datos).execute()
    except Exception as e:
        empresa_id = datos.get("empresa_id", "")
        conn = sqlite3.connect(MASTER_DB)
        conn.execute("INSERT INTO buzon_salida (tabla, operacion, datos, empresa_id) VALUES (?, 'insert', ?, ?)", (tabla, json.dumps(datos), empresa_id))
        conn.commit(); conn.close()

def sync_update_supabase(tabla: str, datos: dict, columna_filtro: str, valor_filtro: str, empresa_id: str):
    try: supabase.table(tabla).update(datos).eq("empresa_id", empresa_id).eq(columna_filtro, valor_filtro).execute()
    except Exception as e:
        conn = sqlite3.connect(MASTER_DB)
        conn.execute("INSERT INTO buzon_salida (tabla, operacion, datos, col_filtro, val_filtro, empresa_id) VALUES (?, 'update', ?, ?, ?, ?)", (tabla, json.dumps(datos), columna_filtro, str(valor_filtro), empresa_id))
        conn.commit(); conn.close()

def sync_delete_supabase(tabla: str, columna_filtro: str, valor_filtro: str, empresa_id: str):
    try: supabase.table(tabla).delete().eq("empresa_id", empresa_id).eq(columna_filtro, valor_filtro).execute()
    except Exception as e:
        conn = sqlite3.connect(MASTER_DB)
        conn.execute("INSERT INTO buzon_salida (tabla, operacion, col_filtro, val_filtro, empresa_id) VALUES (?, 'delete', ?, ?, ?)", (tabla, columna_filtro, str(valor_filtro), empresa_id))
        conn.commit(); conn.close()

def sync_foto_supabase(ruta_local: str, nombre_archivo: str):
    try:
        with open(ruta_local, "rb") as f: supabase.storage.from_("fotos_productos").upload(nombre_archivo, f.read(), {"content-type": "image/jpeg", "x-upsert": "true"})
    except: pass

@app.get("/", response_class=HTMLResponse)
def interfaz(user_role: Optional[str] = Cookie(None), user_name: Optional[str] = Cookie(None), user_business_id: Optional[str] = Cookie(None), user_business_name: Optional[str] = Cookie(None)):
    
    if user_business_id and not os.path.exists(get_db_path(user_business_id)) and user_role != "superadmin":
        user_role = None
        user_business_id = None

    if user_role == "superadmin":
        return """<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Consola Cloud Master</title><link href="/estaticos/bootstrap.min.css" rel="stylesheet"><link rel="stylesheet" href="/estaticos/bootstrap-icons.css"><style>body{background:#0a0a0a;color:white;font-family:'Segoe UI',sans-serif;}.navbar-master{background:#000;border-bottom:1px solid #333;padding:15px;}.card-master{background:#1a1a1a;border:1px solid #333;border-radius:15px;padding:25px;margin-bottom:20px;}input, select{background:#2b2b2b!important;border:1px solid #444!important;color:white!important;}.btn-master{background:#6f42c1;color:white;border:none;font-weight:bold;}.btn-master:hover{background:#59339d;}</style></head><body><div class="navbar-master d-flex justify-content-between align-items-center"><h4 class="m-0 fw-bold text-light"><i class="bi bi-cloud-check-fill text-primary"></i> CONSOLA SUPER ADMIN</h4><button class="btn btn-sm btn-outline-danger fw-bold" onclick="fetch('/logout',{method:'POST'}).then(()=>location.reload())">Cerrar Sesión</button></div><div class="container mt-4"><div class="row"><div class="col-md-5"><div class="card-master"><h5 class="text-primary fw-bold mb-4"><i class="bi bi-building-add"></i> REGISTRAR NUEVO CLIENTE</h5><input type="text" id="ne-nombre" class="form-control mb-3" placeholder="Nombre de la Empresa" autocomplete="off"><div class="text-muted small mb-2">Datos del Dueño:</div><input type="text" id="ne-user" class="form-control mb-3" placeholder="Usuario" autocomplete="off"><input type="password" id="ne-pin" class="form-control mb-3" placeholder="PIN 4 dígitos"><div class="text-muted small mb-2">Giro del Negocio (ADN):</div><select id="ne-giro" class="form-select mb-4 fw-bold text-info"><option value="general">Tienda General / Boutique</option><option value="impresion">Impresión / Taller (Microcom)</option><option value="farmacia">Farmacia / Salud</option><option value="ferreteria">Ferretería / Materiales / Taller</option><option value="abarrotes">Abarrotes / Cremería</option></select><button class="btn btn-master w-100 py-2" onclick="crearEmpresa()">CREAR INSTANCIA</button></div></div><div class="col-md-7"><div class="card-master"><h5 class="text-info fw-bold mb-4"><i class="bi bi-server"></i> EMPRESAS ACTIVAS (HÍBRIDO)</h5><div id="lista-empresas" class="table-responsive">Cargando...</div></div></div></div></div><script>async function cargarEmpresas(){const res=await fetch('/master/empresas');const data=await res.json();let html='<table class="table table-dark table-hover small"><thead><tr><th>ID</th><th>EMPRESA</th><th>GIRO</th><th>CREACIÓN</th></tr></thead><tbody>';data.forEach(e=>{let g=e.giro?e.giro.toUpperCase():'GENERAL';html+=`<tr><td>${e.id}</td><td class="fw-bold">${e.nombre_comercial}</td><td class="text-info">${g}</td><td>${e.fecha_creacion}</td></tr>`;});html+='</tbody></table>';document.getElementById('lista-empresas').innerHTML=html;}async function crearEmpresa(){const n=document.getElementById('ne-nombre').value;const u=document.getElementById('ne-user').value;const p=document.getElementById('ne-pin').value;const g=document.getElementById('ne-giro').value;if(!n||!u||!p)return;const res=await fetch('/master/crear-empresa',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({n,u,p,g})});if((await res.json()).ok)location.reload();}cargarEmpresas();</script></body></html>"""

    if not user_role or not user_business_id:
        return """<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"><title>Portal de Acceso</title><link href="/estaticos/bootstrap.min.css" rel="stylesheet"><style>body{background:#121212;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;font-family:'Segoe UI',sans-serif;}.login-card{background:#1e1e1e;padding:40px;border-radius:20px;box-shadow:0 20px 50px rgba(0,0,0,0.8);width:360px;text-align:center;border:1px solid #333;position:relative;}.btn-login{background:#0d6efd;color:white;font-weight:bold;border-radius:12px;padding:12px;width:100%;border:none;margin-top:15px;}input{width:100%;padding:14px;margin-bottom:15px;background:#2b2b2b;border:1px solid #444;color:white;border-radius:12px;text-align:center;font-size:16px;}.logo-text{color:#fff;font-weight:900;font-size:1.8rem;margin-bottom:5px;letter-spacing:2px;}.sub-text{color:#888;font-size:0.85rem;margin-bottom:25px;}.link-master{position:absolute;bottom:-30px;left:0;right:0;font-size:0.75rem;color:#444;text-decoration:none;cursor:pointer;}#form-master{display:none;}</style></head><body><div class="login-card"><div id="form-pos"><div class="logo-text">PUNTO DE VENTA</div><div class="sub-text">Acceso Local Ultra-Rápido</div><input type="text" id="negocio" placeholder="Nombre de la Empresa" autocomplete="off"><input type="text" id="usuario" placeholder="Usuario" autocomplete="off"><input type="password" id="pin" placeholder="PIN de Acceso"><button class="btn-login" onclick="loginPOS()">INICIAR SESIÓN</button></div><div id="form-master"><div class="logo-text text-primary">CLOUD MASTER</div><div class="sub-text">Acceso Restringido a Servidor</div><input type="text" id="admin-usuario" placeholder="Admin ID" autocomplete="off"><input type="password" id="admin-pin" placeholder="Clave Maestra"><button class="btn-login" style="background:#6f42c1;" onclick="loginMaster()">ENTRAR A CONSOLA</button></div><a class="link-master" onclick="toggleModo()">⚙️ Acceso Servidor</a></div><script>function toggleModo(){const fp=document.getElementById('form-pos');const fm=document.getElementById('form-master');if(fp.style.display==='none'){fp.style.display='block';fm.style.display='none';}else{fp.style.display='none';fm.style.display='block';}}async function loginPOS(){const n=document.getElementById('negocio').value;const u=document.getElementById('usuario').value;const p=document.getElementById('pin').value;if(!n||!u||!p)return;const res=await fetch('/auth',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({u,p,n})});const data=await res.json();if(data.ok)location.reload();else alert(data.msg);}async function loginMaster(){const u=document.getElementById('admin-usuario').value;const p=document.getElementById('admin-pin').value;if(!u||!p)return;const res=await fetch('/auth-master',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({u,p})});if(res.ok)location.reload();else alert('Credenciales de Servidor Denegadas');}</script></body></html>"""

    # --- LECTURA DE CONFIGURACIÓN COMPLETA ---
    conf = {}
    usa_fracciones = "0"
    usa_caducidad = "0"
    usa_taller = "0"
    
    if user_business_id and os.path.exists(get_db_path(user_business_id)):
        try:
            conn = sqlite3.connect(get_db_path(user_business_id))
            res = conn.execute("SELECT parametro, valor FROM configuracion").fetchall()
            conf = {r[0]: r[1] for r in res}
            usa_fracciones = conf.get('usa_fracciones', '0')
            usa_caducidad = conf.get('usa_caducidad', '0')
            usa_taller = conf.get('usa_taller', '0')
            conn.close()
        except: pass

   # Variables para que el ticket nunca salga vacío
    nombre_seguro = urllib.parse.unquote(user_business_name) if user_business_name else "MI NEGOCIO"
    r_social = conf.get('razon_social', nombre_seguro)
    rfc_e = conf.get('rfc_empresa', 'RFC: GENERICO')
    dir_e = conf.get('direccion_empresa', 'Dirección no configurada')
    tel_e = conf.get('telefono_empresa', 'Tel: ---')
    logo_e = conf.get('logo', '')
    msg_e = conf.get('mensaje_ticket', '¡Gracias por su compra!')

    txt_label_cat = "Lote / Registro" if usa_caducidad == "1" else "Categoría"
    txt_placeholder_cat = "Ej. Lote 2026-B1" if usa_caducidad == "1" else "Ej. Impresión, Ropa, Extras..."
    admin_nav_style = "flex" if user_role == "admin" else "none"
    admin_block_style = "block" if user_role == "admin" else "none"
    nombre_comercial = urllib.parse.unquote(user_business_name) if user_business_name else "MI NEGOCIO"
    badge_rol = "ADMINISTRADOR" if user_role == "admin" else "EMPLEADO / CAJERO"
    safe_user_name = user_name if user_name else "Usuario"
    safe_user_role = user_role if user_role else "cajero"
    
    btn_t = '<button class="nav-btn admin-nav-btn" id="btn-taller" onclick="switchTab(\'taller\')"><i class="bi bi-tools"></i><br>TALLER</button>' if usa_taller == "1" else ''
    btn_dtf = '<button class="nav-btn admin-nav-btn" id="btn-dtf" onclick="switchTab(\'dtf\')"><i class="bi bi-printer-fill"></i><br>CALC. DTF</button>' if usa_taller == "1" else ''
    chk_t = '<div class="form-check form-switch bg-warning bg-opacity-25 p-2 rounded mt-2" id="cont-chk-taller"><input class="form-check-input ms-1" type="checkbox" id="chk-taller"><label class="form-check-label fw-bold text-dark ms-2 mt-1" for="chk-taller"><i class="bi bi-tools"></i> Enviar a Taller</label></div>' if usa_taller == "1" else ''

    html_content = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>{EMPRESA_MOSTRADA} - POS Premium</title>
        <link href="/estaticos/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="/estaticos/bootstrap-icons.css">
        <script src="/estaticos/html5-qrcode.min.js"></script>
        <script src="/estaticos/qrcode.min.js"></script>
        <style id="theme-style"></style>
        
        <style>
        
    
            body { background: #f4f7f6; font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; padding-bottom: 100px; color: #334155; transition: all 0.3s ease; }
            .header-pro { background: #ffffff; color: #1e293b; padding: 15px 25px; font-weight: bold; position: sticky; top: 0; z-index: 1000; box-shadow: 0 4px 15px rgba(0,0,0,0.03); border-bottom: 1px solid #e2e8f0; }
            .nav-buttons { background: white; display: flex; justify-content: flex-start; padding: 10px 20px; margin-bottom: 25px; overflow-x: auto; white-space: nowrap; gap: 15px; scrollbar-width: none; box-shadow: 0 4px 6px rgba(0,0,0,0.02); border-bottom: 1px solid #e2e8f0; }
            .nav-buttons::-webkit-scrollbar { display: none; }
            .nav-btn { border: none; background: transparent; color: #64748b; font-weight: 700; font-size: 0.65rem; display: flex; flex-direction: column; align-items: center; min-width: 70px; padding: 8px 10px; border-radius: 12px; transition: all 0.2s ease; }
            .nav-btn:hover { background-color: #f1f5f9; color: #334155; }
            .nav-btn.active { background-color: #ebf5ff; color: #0d6efd; box-shadow: 0 2px 8px rgba(13,110,253,0.15); }
            .nav-btn i { font-size: 1.4rem; margin-bottom: 4px; }
            .card-pro { border-radius: 16px; padding: 18px; background: white; margin-bottom: 12px; border: none; box-shadow: 0 4px 15px rgba(0,0,0,0.04); transition: transform 0.2s, box-shadow 0.2s; }
            .card-pro:hover { transform: translateY(-2px); box-shadow: 0 8px 25px rgba(0,0,0,0.08); }
            .precio-txt { color: #0d6efd; font-weight: 800; font-size: 1.2rem; }
            .cart-container { background: transparent; border: none; padding: 0; max-height: 45vh; overflow-y: auto; }
            .cart-item-card { background: white; border-radius: 14px; padding: 12px 15px; margin-bottom: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.03); border: 1px solid #f1f5f9; transition: all 0.2s; }
            .search-bar-modern { border-radius: 30px 0 0 30px !important; padding-left: 20px !important; border: 1px solid #e2e8f0 !important; border-right: none !important; box-shadow: inset 0 2px 5px rgba(0,0,0,0.01) !important; background: #ffffff !important; }
            .search-bar-modern:focus { border-color: #0d6efd !important; box-shadow: 0 0 0 0.25rem rgba(13,110,253,0.15) !important; }
            .search-btn-modern { border-radius: 0 30px 30px 0 !important; padding-right: 25px !important; border: 1px solid #0d6efd !important; }
            .footer-cobro { position: fixed; bottom: 0; width: 100%; background: white; padding: 15px 25px; border-top: 1px solid #e2e8f0; z-index: 1000; box-shadow: 0 -10px 30px rgba(0,0,0,0.06); }
            .admin-nav-btn { display: {ADMIN_NAV_STYLE} !important; }
            .admin-element { display: {ADMIN_BLOCK_STYLE} !important; }
            .modal-bg { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(15,23,42,0.85); backdrop-filter: blur(4px); display: none; justify-content: center; align-items: center; z-index: 3000; overflow-y: auto; padding: 20px 0; }
            .box-white { background: white; padding: 30px; border-radius: 20px; width: 90%; max-width: 400px; text-align: center; margin: auto; box-shadow: 0 25px 50px -12px rgba(0,0,0,0.25); border: 1px solid #e2e8f0; }
            .kanban-col { background: #f8fafc; border-radius: 16px; padding: 15px; min-width: 280px; width: 33%; max-height: 70vh; overflow-y: auto; border: 1px solid #e2e8f0; }
            .kanban-card { background: white; border-radius: 12px; padding: 15px; margin-bottom: 12px; box-shadow: 0 2px 6px rgba(0,0,0,0.04); border-left: 4px solid #0d6efd; }
            #reader { width: 100%; max-width: 500px; margin: 0 auto; display: none; border-radius: 16px; overflow: hidden; border: 2px solid #e2e8f0; }
            .spin { animation: spin 1s linear infinite; }
            @keyframes spin { 100% { transform: rotate(360deg); } }
            @keyframes slideUp { from { transform: translateY(100%); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
        </style>
    </head>
    <body>
        
        
        <datalist id="dl-clientes"></datalist>
        
        <div class="header-pro d-flex justify-content-between align-items-center">
            <div class="d-flex align-items-center" style="letter-spacing: 0.5px;">
                <div class="bg-primary text-white rounded-circle d-flex justify-content-center align-items-center me-3 shadow-sm" style="width: 38px; height: 38px;"><i class="bi bi-building"></i></div>
                <span class="fs-5">{EMPRESA_MOSTRADA}</span> 
                <span class="badge bg-success ms-3 rounded-pill" style="font-size:0.6rem; letter-spacing: 1px;">LOCAL OFFLINE</span>
                
                <button id="btn-sync" class="btn btn-sm btn-light border ms-3 fw-bold rounded-pill text-secondary shadow-sm" onclick="forzarSincronizacion(this)" style="font-size: 0.7rem;"><i class="bi bi-cloud-arrow-up text-primary"></i> Sincronizar</button>
                

            </div>
            <div class="d-flex align-items-center gap-3">
                <div class="d-flex align-items-center gap-2">
    <div class="input-group input-group-sm shadow-sm" style="width: 160px;">
        <span class="input-group-text bg-white border-secondary text-secondary"><i class="bi bi-palette-fill"></i></span>
        <select class="form-select border-secondary fw-bold" id="selector-tema" onchange="aplicarTemaManual(this.value)" style="font-size: 0.75rem; cursor:pointer;">
            <option value="0">Clásico</option>
            <option value="1">Oscuro Pro</option>
            <option value="2">Azul Medianoche</option>
            <option value="3">Hacker Retro</option>
            <option value="4">CMYK Creativo</option>
            <option value="5">Neón / Open Show</option>
            <option value="6">Café Tostado</option>
            <option value="7">Linux Ubuntu</option>
            <option value="8">Metálico</option>
            <option value="9">Windows XP</option>
            <option value="10">Mac OS</option>
            <option value="11">Premium Dark</option>
        </select>
    </div>
    
</div>
                <div class="text-end d-none d-md-block"><div class="small fw-bold text-dark">{USER_NAME}</div><div style="font-size: 0.65rem; color:#64748b;">{BADGE_ROL}</div></div>
                <button class="btn btn-sm btn-outline-danger border-0 rounded-circle fw-bold shadow-sm bg-white" style="width: 35px; height: 35px;" onclick="cerrarSesion()"><i class="bi bi-power"></i></button>
            </div>
        </div>

        <div class="nav-buttons">
            <button class="nav-btn active" id="btn-venta" onclick="switchTab('venta')"><i class="bi bi-cart-fill"></i>VENTA</button>
            <button class="nav-btn admin-nav-btn" id="btn-ofertas" onclick="switchTab('ofertas')"><i class="bi bi-tags-fill"></i>OFERTAS</button>
            <button class="nav-btn admin-nav-btn" id="btn-excel" onclick="switchTab('excel')"><i class="bi bi-file-earmark-spreadsheet-fill"></i>EXCEL</button>
            <button class="nav-btn admin-nav-btn" id="btn-clientes" onclick="switchTab('clientes')"><i class="bi bi-people-fill"></i>CLIENTES</button>
            {BTN_TALLER}
            {BTN_DTF}
            <button class="nav-btn" id="btn-cotizaciones" onclick="switchTab('cotizaciones')"><i class="bi bi-file-earmark-text-fill"></i>COTIZAC.</button>
            <button class="nav-btn" id="btn-consultas" onclick="switchTab('consultas')"><i class="bi bi-search"></i>PRECIOS</button>
            <button class="nav-btn admin-nav-btn" id="btn-pendientes" onclick="switchTab('pendientes')"><i class="bi bi-hourglass-split"></i>DEUDAS</button>
            <button class="nav-btn admin-nav-btn" id="btn-historial" onclick="switchTab('historial')"><i class="bi bi-receipt"></i>NOTAS</button>
            <button class="nav-btn admin-nav-btn" id="btn-inventario" onclick="switchTab('inventario')"><i class="bi bi-box-seam-fill"></i>ENTRADAS</button>
            <button class="nav-btn admin-nav-btn" id="btn-ajustes" onclick="switchTab('ajustes')"><i class="bi bi-sliders"></i>AJUSTES</button>
            <button class="nav-btn" id="btn-reportes" onclick="switchTab('reportes')"><i class="bi bi-safe-fill"></i>CAJA</button>
            <button class="nav-btn admin-nav-btn" id="btn-usuarios" onclick="switchTab('usuarios')"><i class="bi bi-person-badge-fill"></i>EQUIPO</button><button class="nav-btn admin-nav-btn" id="btn-config-sistem" onclick="switchTab('config-sistem')"><i class="bi bi-gear-fill"></i><br>CONFIG</button>
        </div>
        
        <div class="container pb-5">
            <div id="reader" class="mb-3 shadow-sm"></div>
            <button id="stop-scan" class="btn btn-danger w-100 mb-4 fw-bold shadow-sm rounded-pill" style="display:none; padding: 12px;" onclick="detenerEscaneo()"><i class="bi bi-x-octagon-fill"></i> DETENER CÁMARA</button>

            <div id="tab-venta">
                <div class="input-group mb-3 shadow-sm" style="border-radius: 30px;"><input type="text" id="bus-v" class="form-control form-control-lg search-bar-modern" placeholder="Buscar código o artículo (F2)..." onkeyup="ejecutarBusqueda(this.value, 'res-v', 'venta')" autocomplete="off"><button class="btn btn-primary search-btn-modern fw-bold" onclick="iniciarEscaneo('venta')"><i class="bi bi-upc-scan fs-5"></i></button></div>
                <div class="d-flex justify-content-between align-items-center mb-4">
                    <button class="btn btn-light fw-bold py-2 shadow-sm rounded-pill border" onclick="abrirTemporal()" style="color: #64748b; font-size: 0.85rem; width: 60%;"><i class="bi bi-plus-circle-fill text-primary me-1"></i> VENTA RÁPIDA (F6)</button>
                    <div class="form-check form-switch bg-warning bg-opacity-10 px-3 py-2 rounded-pill border border-warning border-opacity-50" style="width: 38%;">
                        <input class="form-check-input ms-0 me-2" type="checkbox" id="chk-vip" onchange="actualizarVistaCarrito()" style="cursor:pointer; width: 2em;">
                        <label class="form-check-label fw-bold text-dark mt-1" style="font-size:0.75rem; cursor:pointer;" for="chk-vip"><i class="bi bi-star-fill text-warning"></i> PRECIO VIP</label>
                    </div>
                </div>
                <div id="res-v"></div>
                <div id="carrito-seccion" style="display:none;" class="pb-4 mt-2">
                    <div class="d-flex justify-content-between align-items-end mb-3 px-1"><h6 class="text-secondary fw-bold m-0"><i class="bi bi-bag-check-fill text-primary"></i> TU CARRITO</h6><small class="text-muted fw-bold" style="font-size: 0.7rem;"><i class="bi bi-keyboard"></i> Presiona F3 para editar</small></div>
                    <div id="items-carrito" class="cart-container"></div>
                </div>
            </div>

            <div id="tab-dtf" style="display:none;">
                <div class="card-pro mb-4" style="background: linear-gradient(145deg, #f8fafc, #f1f5f9);">
                    <h5 class="fw-bold text-primary mb-3"><i class="bi bi-calculator-fill"></i> COTIZADOR DE IMPRESIÓN DTF</h5>
                    <div class="row g-3">
                        <div class="col-12"><h6 class="fw-bold text-secondary border-bottom pb-2 mt-2"><i class="bi bi-box-seam text-primary"></i> Tus Costos Reales (Insumos)</h6></div>
                        <div class="col-6"><label class="small fw-bold text-muted ps-2">Ancho del Film (cm)</label><input type="number" id="dtf-ancho-film" class="form-control rounded-pill text-center bg-white border-0 shadow-sm" value="60"></div>
                        <div class="col-6"><label class="small fw-bold text-muted ps-2">Costo Metro Lineal ($)</label><input type="number" id="dtf-costo-film" class="form-control rounded-pill text-center bg-white border-0 shadow-sm" value="80"></div>
                        <div class="col-6"><label class="small fw-bold text-muted ps-2">Costo Tinta / Litro ($)</label><input type="number" id="dtf-costo-tinta" class="form-control rounded-pill text-center bg-white border-0 shadow-sm" value="1200"></div>
                        <div class="col-6"><label class="small fw-bold text-muted ps-2">Costo Polvo / Kilo ($)</label><input type="number" id="dtf-costo-polvo" class="form-control rounded-pill text-center bg-white border-0 shadow-sm" value="600"></div>
                        <div class="col-12"><h6 class="fw-bold text-secondary border-bottom pb-2 mt-4"><i class="bi bi-rulers text-primary"></i> Medidas del Cliente</h6></div>
                        <div class="col-4"><label class="small fw-bold text-dark ps-2">Ancho (cm)</label><input type="number" id="dtf-ancho-cliente" class="form-control rounded-pill text-center fw-bold border-primary border-opacity-50 text-primary" onkeyup="calcularDTF()"></div>
                        <div class="col-4"><label class="small fw-bold text-dark ps-2">Largo (cm)</label><input type="number" id="dtf-largo-cliente" class="form-control rounded-pill text-center fw-bold border-primary border-opacity-50 text-primary" onkeyup="calcularDTF()"></div>
                        <div class="col-4"><label class="small fw-bold text-danger ps-2">Ganancia (%)</label><input type="number" id="dtf-margen" class="form-control rounded-pill text-center fw-bold bg-danger bg-opacity-10 border-0 text-danger" value="300" onkeyup="calcularDTF()"></div>
                        <div class="col-12 mt-4"><div class="bg-white p-3 rounded-4 shadow-sm border border-light text-center"><div class="row"><div class="col-6 border-end"><small class="text-muted fw-bold d-block mb-1">Costo de Producción:</small><h4 class="text-danger fw-bold m-0" id="dtf-res-costo">$0.00</h4></div><div class="col-6"><small class="text-muted fw-bold d-block mb-1">Cobrar al Cliente:</small><h3 class="text-success fw-bold m-0" id="dtf-res-venta">$0.00</h3></div></div></div></div>
                        <div class="col-12 mt-3"><button class="btn btn-primary w-100 fw-bold py-3 rounded-pill shadow-sm fs-6" onclick="agregarAlTicketDTF()"><i class="bi bi-cart-plus-fill me-2 fs-5"></i> AÑADIR A LA VENTA</button></div>
                    </div>
                </div>
            </div>

            <div id="tab-ofertas" style="display:none;"><div class="card-pro mb-4" style="background: linear-gradient(145deg, #fffbeb, #fef3c7);"><h6 class="fw-bold text-warning text-darken mb-3"><i class="bi bi-star-fill"></i> CREAR OFERTA O COMBO</h6><div class="row g-3"><div class="col-12"><div class="input-group shadow-sm" style="border-radius: 30px;"><input type="text" id="promo-cod" class="form-control search-bar-modern" placeholder="Buscar por Nombre o Código..." onkeyup="ejecutarBusqueda(this.value, 'res-promo', 'promo')" autocomplete="off"><button class="btn btn-primary search-btn-modern" onclick="iniciarEscaneo('promo')"><i class="bi bi-upc-scan"></i></button></div><div id="res-promo" class="mt-2" style="max-height: 25vh; overflow-y: auto;"></div><div id="promo-desc-lbl" class="mt-1 small fw-bold px-2"></div></div><div class="col-6"><label class="small fw-bold text-muted ps-2">Cantidad <small>(Llevan)</small></label><input type="number" id="promo-cant" class="form-control fw-bold text-center rounded-pill" value="1"></div><div class="col-6"><label class="small fw-bold text-muted ps-2">Precio Total $ <small>(Pagan)</small></label><input type="number" id="promo-precio" class="form-control fw-bold text-success text-center rounded-pill"></div><div class="col-6"><label class="small fw-bold text-muted ps-2">Inicia</label><input type="date" id="promo-inicio" class="form-control rounded-pill"></div><div class="col-6"><label class="small fw-bold text-muted ps-2">Termina</label><input type="date" id="promo-fin" class="form-control rounded-pill"></div><div class="col-12 mt-4"><button class="btn btn-warning w-100 fw-bold text-dark shadow-sm py-3 rounded-pill" onclick="crearPromocion()">GUARDAR PROMOCIÓN</button></div></div></div><h6 class="fw-bold text-secondary mb-3 ps-1"><i class="bi bi-tags"></i> OFERTAS ACTIVAS:</h6><div id="lista-promociones"></div></div>
            
            <div id="tab-excel" style="display:none;">
                <div class="card-pro mb-4" style="background: linear-gradient(145deg, #f0fdf4, #dcfce7);">
                    <h6 class="fw-bold text-success mb-3"><i class="bi bi-file-earmark-excel-fill"></i> IMPORTAR / EXPORTAR (CSV)</h6>
                    <button class="btn btn-success w-100 fw-bold mb-3 rounded-pill py-2 shadow-sm" onclick="window.location.href='/exportar-inventario'">
                        <i class="bi bi-cloud-download-fill"></i> DESCARGAR INVENTARIO
                    </button>
                    <div class="border-top border-success border-opacity-25 pt-4 mt-2">
                        <div class="input-group shadow-sm" style="border-radius: 30px;">
                            <input type="file" id="archivo-csv" class="form-control" style="border-radius: 30px 0 0 30px;" accept=".csv">
                            <button class="btn btn-dark fw-bold px-4" style="border-radius: 0 30px 30px 0;" onclick="subirCSV()">
                                <i class="bi bi-cloud-upload-fill"></i> SUBIR
                            </button>
                        </div>
                    </div>
                </div>

                <div class="card-pro mb-4" style="background: white; border: 1px solid #dcfce7;">
                    <h6 class="fw-bold text-success mb-3"><i class="bi bi-images"></i> CARGA MASIVA DE FOTOS</h6>
                    <p class="small text-muted">1. Pon tus fotos en la carpeta <b>"CargarFotos"</b>.<br>2. El nombre de la foto debe ser el <b>Código</b> del producto (ej: 7501.jpg).</p>
                    <button class="btn btn-outline-success w-100 fw-bold rounded-pill py-2" onclick="ejecutarCargaMasivaFotos()">
                        <i class="bi bi-magic"></i> VINCULAR FOTOS AHORA
                    </button>
                </div>
            </div> 

            <div id="tab-clientes" style="display:none;"><div class="card-pro mb-4" style="background: #f8fafc;"><h6 class="fw-bold text-primary mb-3"><i class="bi bi-person-plus-fill"></i> NUEVO CLIENTE</h6><div class="row g-3"><div class="col-12"><input type="text" id="nc-nombre" class="form-control rounded-pill px-3" placeholder="Nombre completo o Empresa *" autocomplete="off"></div><div class="col-6"><input type="text" id="nc-tel" class="form-control rounded-pill px-3" placeholder="Teléfono / WhatsApp"></div><div class="col-6"><input type="email" id="nc-correo" class="form-control rounded-pill px-3" placeholder="Correo Electrónico"></div><div class="col-12"><button class="btn btn-primary w-100 fw-bold py-2 rounded-pill shadow-sm" onclick="crearCliente()"><i class="bi bi-floppy"></i> GUARDAR CLIENTE</button></div></div></div><div class="input-group mb-4 shadow-sm" style="border-radius: 30px;"><span class="input-group-text bg-white border-0 ps-4 text-muted" style="border-radius: 30px 0 0 30px;"><i class="bi bi-search"></i></span><input type="text" class="form-control border-0 px-2" style="border-radius: 0 30px 30px 0;" placeholder="Buscar en directorio..." onkeyup="filtrarClientes(this.value)" autocomplete="off"></div><div id="lista-directorio-clientes"></div></div>
            <div id="tab-taller" style="display:none;"><div class="d-flex justify-content-between align-items-center mb-3 px-2"><h5 class="fw-bold text-primary m-0"><i class="bi bi-kanban-fill"></i> TABLERO TALLER</h5><button class="btn btn-sm btn-light border fw-bold rounded-pill shadow-sm text-secondary" onclick="cargarTaller()"><i class="bi bi-arrow-clockwise text-primary"></i> Recargar</button></div><div class="d-flex gap-3 overflow-auto pb-3"><div class="kanban-col"><h6 class="fw-bold text-secondary text-center border-bottom pb-2 mb-3">📋 EN FILA</h6><div id="kb-fila"></div></div><div class="kanban-col" style="background: #fffbeb; border-color: #fef08a;"><h6 class="fw-bold text-warning text-center border-bottom border-warning border-opacity-25 pb-2 mb-3">⚙️ EN PRODUCCIÓN</h6><div id="kb-produccion"></div></div><div class="kanban-col" style="background: #f0fdf4; border-color: #bbf7d0;"><h6 class="fw-bold text-success text-center border-bottom border-success border-opacity-25 pb-2 mb-3">✅ LISTO P/ ENTREGAR</h6><div id="kb-listo"></div></div></div></div>
            <div id="tab-cotizaciones" style="display:none;"><h6 class="fw-bold text-secondary mb-3 ps-2"><i class="bi bi-journal-text"></i> TUS COTIZACIONES:</h6><div id="lista-cotizaciones"></div></div>
            <div id="tab-consultas" style="display:none;"><div class="input-group mb-4 shadow-sm" style="border-radius: 30px;"><input type="text" id="bus-c" class="form-control form-control-lg search-bar-modern" placeholder="Verificador de Precios y Stock..." onkeyup="ejecutarBusqueda(this.value, 'res-c', 'consulta')" autocomplete="off"><button class="btn btn-primary search-btn-modern" onclick="iniciarEscaneo('consulta')"><i class="bi bi-upc-scan fs-5"></i></button></div><div id="res-c"></div></div>
            <div id="tab-pendientes" style="display:none;"><h6 class="fw-bold text-secondary mb-3 ps-2"><i class="bi bi-wallet2"></i> CUENTAS POR COBRAR:</h6><div id="lista-pendientes"></div></div>
            <div id="tab-historial" style="display:none;"><h6 class="fw-bold text-secondary mb-3 ps-2"><i class="bi bi-clock-history"></i> NOTAS HISTÓRICAS:</h6><div id="lista-historial"></div></div>
            
            <div id="tab-inventario" style="display:none;">
                <div class="card-pro mb-4 bg-white">
                    <h5 class="fw-bold text-primary mb-4 border-bottom pb-3"><i class="bi bi-box-arrow-in-down"></i> REGISTRO DE MERCANCÍA</h5>
                    <div class="row g-3">
                        <div class="col-md-6"><label class="small fw-bold text-muted ps-2">Código de Barras *</label><div class="input-group shadow-sm" style="border-radius: 30px;"><input type="text" id="np-cod" class="form-control search-bar-modern" placeholder="Escanear o teclear..." onchange="verificarCodigoEntrada(this.value)" autocomplete="off"><button class="btn btn-primary search-btn-modern" onclick="iniciarEscaneo('entrada')"><i class="bi bi-upc-scan"></i></button></div></div>
                        <div class="col-md-6"><label class="small fw-bold text-muted ps-2">Descripción del Artículo *</label><input type="text" id="np-desc" class="form-control rounded-pill px-3 bg-light border-0" placeholder="Nombre completo" onchange="verificarCodigoEntrada(this.value)" autocomplete="off"></div>
                        <div class="col-md-12"><label class="small fw-bold text-muted ps-2"><i class="bi bi-image text-primary"></i> Foto del Producto (Opcional)</label><input type="file" id="np-foto" class="form-control rounded-pill bg-light border-0 px-3" accept="image/*"></div>
                        <div class="col-md-12" id="cont-caducidad" style="display:none;"><label class="small fw-bold text-danger ps-2"><i class="bi bi-calendar-x"></i> Fecha de Caducidad (Lote)</label><input type="date" id="np-caducidad" class="form-control rounded-pill border-danger border-opacity-50 text-danger bg-danger bg-opacity-10 px-3"></div>
                        <div class="col-md-4"><label class="small fw-bold text-muted ps-2">{TXT_LABEL_CAT}</label><input type="text" id="np-cat" class="form-control rounded-pill px-3 bg-light border-0" placeholder="{TXT_PLACEHOLDER_CAT}" autocomplete="off"></div>
                        <div class="col-md-4"><label class="small fw-bold text-primary ps-2"><i class="bi bi-rulers"></i> Unidad *</label><select id="np-unidad" class="form-select rounded-pill px-3 fw-bold border-primary text-primary bg-primary bg-opacity-10"><option value="PZ">PZ - Pieza</option><option value="KG">KG - Kilo</option><option value="LT">LT - Litro</option><option value="MT">MT - Metro</option><option value="SRV">SRV - Servicio</option></select></div>
                        <div class="col-md-4"><label class="small fw-bold text-muted ps-2">Fecha Ingreso</label><input type="date" id="np-fecha" class="form-control rounded-pill px-3 bg-light border-0 text-muted"></div>
                        
                        <div class="col-md-4"><label class="small fw-bold text-primary ps-2">Precio Venta 1 ($) * <span id="lbl-utilidad" class="badge bg-success ms-1 fw-bold rounded-pill">Ganancia: --</span></label><input type="number" id="np-pre" class="form-control rounded-pill px-3 fw-bold text-primary border-primary border-opacity-50" placeholder="0.00" onkeyup="calcularUtilidad()"></div>
                        <div class="col-md-4"><label class="small fw-bold text-muted ps-2">Costo Compra ($)</label><input type="number" id="np-costo" class="form-control rounded-pill px-3 bg-light border-0" value="0" onkeyup="calcularUtilidad()"></div>
                        <div class="col-md-4"><label class="small fw-bold text-success ps-2">Unidades Nuevas *</label><input type="number" id="np-stock" class="form-control rounded-pill px-3 fw-bold text-success border-success border-opacity-50" value="0"></div>
                        
                        <div class="col-12 mt-3"><h6 class="fw-bold text-secondary mb-2 border-bottom pb-2"><i class="bi bi-tags-fill text-primary"></i> Precios de Mayoreo y Especiales</h6></div>
                        <div class="col-md-3"><label class="small fw-bold text-muted ps-2">Precio 2 ($)</label><input type="number" id="np-p2" class="form-control rounded-pill px-3 bg-light border-0" placeholder="0.00"></div>
                        <div class="col-md-3"><label class="small fw-bold text-muted ps-2">A partir de (Cant)</label><input type="number" id="np-cp2" class="form-control rounded-pill px-3 bg-light border-0" placeholder="Ej. 3"></div>
                        <div class="col-md-3"><label class="small fw-bold text-muted ps-2">Precio 3 ($)</label><input type="number" id="np-p3" class="form-control rounded-pill px-3 bg-light border-0" placeholder="0.00"></div>
                        <div class="col-md-3"><label class="small fw-bold text-muted ps-2">A partir de (Cant)</label><input type="number" id="np-cp3" class="form-control rounded-pill px-3 bg-light border-0" placeholder="Ej. 12"></div>
                        <div class="col-md-6 mt-3"><label class="small fw-bold text-primary ps-2"><i class="bi bi-star-fill text-warning"></i> Precio Especial (VIP) $</label><input type="number" id="np-pe" class="form-control rounded-pill px-3 fw-bold border-warning border-opacity-50" placeholder="0.00"></div>
                        
                        <div class="col-12 mt-4"><h6 class="fw-bold text-secondary mb-3 border-bottom pb-2"><i class="bi bi-truck text-primary"></i> Datos del Proveedor (Opcional)</h6></div>
                        <div class="col-md-4"><input type="text" id="np-prov" class="form-control rounded-pill px-3 bg-light border-0" placeholder="Nombre Proveedor" autocomplete="off"></div>
                        <div class="col-md-4"><input type="text" id="np-wa" class="form-control rounded-pill px-3 bg-light border-0" placeholder="WhatsApp (Ej. 551234...)"></div>
                        <div class="col-md-4"><input type="email" id="np-mail" class="form-control rounded-pill px-3 bg-light border-0" placeholder="Correo"></div>
                        
                        <div class="col-12 mt-4"><button class="btn btn-primary w-100 fw-bold py-3 rounded-pill shadow-sm fs-6" onclick="crearProducto()"><i class="bi bi-check2-circle fs-5 me-1"></i> INGRESAR AL INVENTARIO</button></div>
                    </div>
                </div>
            </div>
            
            <div id="tab-ajustes" style="display:none;"><h6 class="fw-bold text-primary mb-3 ps-2"><i class="bi bi-sliders"></i> ACTUALIZACIÓN RÁPIDA DE STOCK</h6><div class="input-group mb-4 shadow-sm" style="border-radius: 30px;"><input type="text" id="bus-ajustes" class="form-control form-control-lg search-bar-modern" placeholder="Buscar para editar..." onkeyup="ejecutarBusquedaAjustes(this.value)" autocomplete="off"><button class="btn btn-primary search-btn-modern" onclick="iniciarEscaneo('ajustes')"><i class="bi bi-upc-scan fs-5"></i></button></div><div id="barra-masiva" style="display:none; background: linear-gradient(145deg, #0d6efd, #0b5ed7); border-radius: 20px; padding: 15px 20px;" class="mb-4 justify-content-between align-items-center shadow"><span class="fw-bold text-white"><i class="bi bi-check-circle-fill me-2"></i> <span id="count-seleccionados" class="fs-5">0</span> seleccionados</span><button class="btn btn-light btn-sm fw-bold px-4 py-2 rounded-pill text-primary shadow-sm" onclick="abrirModalMasivo()">EDITAR SELECCIÓN</button></div><div id="res-ajustes"></div></div>
            
<div id="tab-config-sistem" style="display:none;">
                <div class="card-pro mb-4">
                    <h5 class="fw-bold text-primary mb-3"><i class="bi bi-building-gear"></i> CONFIGURACIÓN DEL TICKET</h5>
                    <div class="row g-3">
                        <div class="col-md-6"><label class="small fw-bold text-muted ps-2">Razón Social</label><input type="text" id="cfg-razon" class="form-control rounded-pill px-3 bg-light border-0" value="{RS_E}"></div>
                        <div class="col-md-6"><label class="small fw-bold text-muted ps-2">RFC</label><input type="text" id="cfg-rfc" class="form-control rounded-pill px-3 bg-light border-0" value="{RFC_E}"></div>
                        <div class="col-12"><label class="small fw-bold text-muted ps-2">Dirección Completa</label><input type="text" id="cfg-dir" class="form-control rounded-pill px-3 bg-light border-0" value="{DIR_E}"></div>
                        <div class="col-md-6"><label class="small fw-bold text-muted ps-2">Teléfono</label><input type="text" id="cfg-tel" class="form-control rounded-pill px-3 bg-light border-0" value="{TEL_E}"></div>
                        <div class="col-md-6"><label class="small fw-bold">Ruta o URL del Logo:</label><input type="text" id="cfg-logo" class="form-control" placeholder="./assets/logo.png" value="{LOGO_E}"></div>
                        <div class="col-md-6"><label class="small fw-bold text-muted ps-2">Mensaje de Agradecimiento</label><input type="text" id="cfg-msg" class="form-control rounded-pill px-3 bg-light border-0" value="{MSG_E}"></div>
                        <div class="col-12 mt-4"><button class="btn btn-primary w-100 fw-bold py-3 rounded-pill shadow-sm" onclick="guardarConfigSistem()">💾 GUARDAR CONFIGURACIÓN</button></div>
                    </div>
                </div>
            </div>

            <div id="tab-config-sistem" style="display:none;"><div class="card-pro mb-4 bg-white"><h5 class="fw-bold text-primary mb-3"><i class="bi bi-building-gear"></i> CONFIGURACIÓN DEL TICKET</h5><div class="row g-3"><div class="col-md-6"><label class="small fw-bold text-muted ps-2">Razón Social</label><input type="text" id="cfg-razon" class="form-control rounded-pill px-3 bg-light border-0"></div><div class="col-md-6"><label class="small fw-bold text-muted ps-2">RFC</label><input type="text" id="cfg-rfc" class="form-control rounded-pill px-3 bg-light border-0"></div><div class="col-12"><label class="small fw-bold text-muted ps-2">Dirección Completa</label><input type="text" id="cfg-dir" class="form-control rounded-pill px-3 bg-light border-0"></div><div class="col-md-6"><label class="small fw-bold text-muted ps-2">Teléfono</label><input type="text" id="cfg-tel" class="form-control rounded-pill px-3 bg-light border-0"></div><div class="col-md-6"><label class="small fw-bold text-muted ps-2">Mensaje de Agradecimiento</label><input type="text" id="cfg-msg" class="form-control rounded-pill px-3 bg-light border-0"></div><div class="col-12 mt-4"><button class="btn btn-primary w-100 fw-bold py-3 rounded-pill shadow-sm" onclick="guardarConfigSistem()"><i class="bi bi-save"></i> GUARDAR CONFIGURACIÓN</button></div></div></div></div>
            <div id="tab-reportes" style="display:none;">
                <h5 class="fw-bold text-primary mb-3 ps-2"><i class="bi bi-safe-fill"></i> CAJA Y CORTE</h5>
                <div class="card-pro text-center mb-4" style="background: linear-gradient(145deg, #1e293b, #0f172a); color: white; padding: 25px; border-radius: 24px; box-shadow: 0 10px 25px rgba(0,0,0,0.15);">
                    <div class="fw-bold text-warning mb-1" style="font-size: 1.1rem;"><i class="bi bi-person-circle"></i> TURNO: {USER_NAME}</div>
                    <div class="text-light opacity-50 small mb-4">Movimientos de tu sesión actual</div>
                    <div class="row text-start px-3 mb-4"><div class="col-6 small text-light opacity-75 mb-2">📥 Fondo Inicial:</div><div class="col-6 small fw-bold text-end mb-2 text-info" id="turno-fon" onclick="registrarFondo()" style="cursor:pointer;" title="Clic para agregar morralla">$0.00</div><div class="col-6 small text-light opacity-75 mb-2">💵 Efectivo Venta:</div><div class="col-6 small fw-bold text-end mb-2" id="turno-efe">$0.00</div><div class="col-6 small text-light opacity-75 mb-2">💳 Tarjeta:</div><div class="col-6 small fw-bold text-end mb-2" id="turno-tar">$0.00</div><div class="col-6 small text-danger opacity-75">🔻 Retiros:</div><div class="col-6 small fw-bold text-danger text-end" id="turno-gas">-$0.00</div></div>
                    <div class="bg-black bg-opacity-50 p-4 rounded-4 mb-4 border border-secondary border-opacity-25"><div class="small fw-bold text-light opacity-75 mb-1">EFECTIVO EN CAJÓN</div><h2 class="fw-bold text-success m-0" id="turno-cajon">$0.00</h2></div>
                    <div class="d-flex gap-3"><button class="btn btn-danger w-50 fw-bold rounded-pill py-2" onclick="registrarGasto()"><i class="bi bi-dash-circle"></i> RETIRO</button><button class="btn btn-warning w-50 fw-bold text-dark rounded-pill py-2 shadow-sm" onclick="cerrarTurno()"><i class="bi bi-printer-fill"></i> CORTE Z</button></div>
                </div>
                <div class="admin-element">
                    <h6 class="fw-bold text-secondary mt-5 mb-3 border-top pt-4 ps-2"><i class="bi bi-bar-chart-line-fill"></i> MÉTRICAS GLOBALES</h6>
                    <button class="btn btn-light w-100 fw-bold shadow-sm py-3 text-primary mb-4 rounded-pill border" onclick="generarListaCompras()"><i class="bi bi-cart-x-fill me-2"></i> VER ARTÍCULOS AGOTADOS</button>
                    <div class="card-pro shadow-sm mb-4"><div class="row g-2 align-items-center"><div class="col-4"><small class="text-muted fw-bold ps-2">Desde:</small><input type="date" id="rep-inicio" class="form-control rounded-pill bg-light border-0"></div><div class="col-4"><small class="text-muted fw-bold ps-2">Hasta:</small><input type="date" id="rep-fin" class="form-control rounded-pill bg-light border-0"></div><div class="col-4"><small class="text-muted fw-bold ps-2">Cajero:</small><select id="rep-cajero" class="form-select rounded-pill bg-primary bg-opacity-10 text-primary fw-bold border-0"><option value="TODOS">Todos</option></select></div><div class="col-12 mt-3"><button class="btn btn-primary w-100 fw-bold py-2 rounded-pill shadow-sm" onclick="cargarReportes()"><i class="bi bi-search"></i> GENERAR REPORTE</button></div></div></div>
                    <div class="row g-3 mb-4"><div class="col-6"><div class="card-pro text-center shadow-sm" style="background: linear-gradient(145deg, #eff6ff, #dbeafe); padding: 20px 10px;"><div class="fw-bold text-primary opacity-75 mb-1" style="font-size:0.7rem;"><i class="bi bi-cash-stack"></i> VENTAS BRUTAS</div><h4 class="fw-bold m-0 text-primary" id="rep-total-ventas">$0.00</h4><div class="mt-3 border-top border-primary border-opacity-10 pt-2 text-start px-2" style="font-size: 0.75rem;"><div class="text-secondary fw-bold">Efe: <span id="rep-efectivo" class="float-end text-dark">$0.00</span></div><div class="text-secondary fw-bold mt-1">Trans: <span id="rep-transferencia" class="float-end text-dark">$0.00</span></div></div></div></div><div class="col-6"><div class="card-pro text-center shadow-sm" style="background: linear-gradient(145deg, #f0fdf4, #dcfce7); border: 1px solid #bbf7d0; padding: 20px 10px; height: 100%;"><div class="fw-bold text-success opacity-75 mb-1" style="font-size:0.7rem;"><i class="bi bi-graph-up-arrow"></i> UTILIDAD NETA</div><h4 class="fw-bold m-0 text-success" id="rep-utilidad">$0.00</h4><div class="mt-3 text-muted fw-bold bg-white rounded-pill py-1 mx-2 shadow-sm" style="font-size: 0.75rem;" id="rep-conteo">0 items</div></div></div></div>
                    <h6 class="fw-bold text-secondary mt-4 mb-3 ps-2"><i class="bi bi-list-columns-reverse"></i> DESGLOSE:</h6>
                    <div class="table-responsive bg-white rounded-4 shadow-sm border border-light p-1"><table class="table table-sm table-hover mb-0" style="font-size: 0.8rem;"><thead class="table-light text-muted"><tr><th class="ps-3 border-0">Fecha</th><th class="border-0">Producto</th><th class="text-center border-0">Cant.</th><th class="border-0">Total</th><th class="pe-3 border-0">Cajero</th></tr></thead><tbody id="tabla-reporte-cuerpo" class="border-top-0"></tbody></table></div>
                </div>
            </div>

            <div id="tab-usuarios" style="display:none;"><div class="card-pro mb-4 bg-white"><h6 class="fw-bold text-primary mb-3"><i class="bi bi-person-plus-fill"></i> REGISTRAR EMPLEADO</h6><input type="text" id="nu-nombre" class="form-control rounded-pill px-3 bg-light border-0 mb-3" placeholder="Nombre del trabajador"><input type="number" id="nu-pin" class="form-control rounded-pill px-3 bg-light border-0 mb-3" placeholder="PIN Secreto (4 dígitos)"><select id="nu-rol" class="form-select rounded-pill px-3 mb-4 fw-bold text-secondary bg-light border-0"><option value="cajero">CAJERO (Mostrador)</option><option value="admin">ADMINISTRADOR (Todo)</option></select><button class="btn btn-primary w-100 fw-bold rounded-pill py-2 shadow-sm" onclick="crearUsuario()"><i class="bi bi-check-lg"></i> GUARDAR ACCESO</button></div><h6 class="fw-bold text-secondary mb-3 ps-2"><i class="bi bi-people"></i> TU EQUIPO:</h6><div id="lista-equipo"></div></div>
        </div>

        <!-- MODALES REDISEÑADOS -->
        <div id="modalDuplicado" class="modal-bg"><div class="box-white"><div class="bg-danger text-white rounded-circle d-flex justify-content-center align-items-center mx-auto mb-3 shadow" style="width:60px; height:60px;"><i class="bi bi-x-lg fs-1"></i></div><h4 class="fw-bold text-dark mb-2">PRODUCTO EXISTENTE</h4><p class="text-muted small mb-4">Este artículo ya está en tu base de datos:</p><div class="bg-light p-3 rounded-4 text-start mb-4 border border-light"><div class="small text-muted fw-bold">CÓDIGO: <span id="dup-cod" class="text-dark fs-6 ms-1"></span></div><div class="small text-muted fw-bold mt-2">ARTÍCULO: <span id="dup-desc" class="text-dark fs-6 ms-1"></span></div><div class="row mt-2"><div class="col-6 small text-muted fw-bold">PRECIO: <span id="dup-pre" class="text-primary fs-6 ms-1"></span></div><div class="col-6 small text-muted fw-bold">STOCK: <span id="dup-stock" class="text-success fs-6 ms-1"></span></div></div></div><button class="btn btn-warning btn-lg w-100 fw-bold shadow-sm rounded-pill text-dark" onclick="cerrarModalDuplicado()"><i class="bi bi-arrow-return-left me-1"></i> ENTENDIDO</button></div></div>
        <div id="modalCompras" class="modal-bg"><div class="box-white p-4" style="width: 95%; max-width: 500px;"><div class="bg-warning text-dark rounded-circle d-flex justify-content-center align-items-center mx-auto mb-3 shadow-sm" style="width:50px; height:50px;"><i class="bi bi-cart-x fs-2"></i></div><h5 class="fw-bold text-dark mb-1">LISTA URGENTE</h5><div class="text-muted small mb-4">Artículos con 5 o menos unidades.</div><div id="lista-compras-content" class="text-start mb-4 bg-light rounded-4 p-2 border border-light" style="max-height: 40vh; overflow-y: auto;"></div><button class="btn btn-success w-100 fw-bold mb-2 shadow-sm py-3 rounded-pill" onclick="enviarListaWhatsApp()"><i class="bi bi-whatsapp me-1"></i> ENVIAR AL PROVEEDOR</button><button class="btn btn-link text-muted w-100 text-decoration-none fw-bold" onclick="document.getElementById('modalCompras').style.display='none'">Cerrar</button></div></div>
        <div id="modalRetiro" class="modal-bg"><div class="box-white p-4"><div class="bg-danger bg-opacity-10 text-danger rounded-circle d-flex justify-content-center align-items-center mx-auto mb-3" style="width:50px; height:50px;"><i class="bi bi-dash-lg fs-2"></i></div><h5 class="fw-bold text-dark mb-4">RETIRO DE CAJA</h5><input type="text" id="desc-gasto" class="form-control rounded-pill px-3 bg-light border-0 mb-3" placeholder="Motivo (Ej. Pago de luz)"><input type="number" id="monto-gasto" class="form-control rounded-pill px-3 mb-4 text-center fs-3 text-danger fw-bold border-danger border-opacity-50 bg-white shadow-sm" placeholder="$ 0.00"><button class="btn btn-danger w-100 fw-bold py-3 rounded-pill shadow-sm mb-2" onclick="confirmarGasto()">REGISTRAR RETIRO</button><button class="btn btn-link text-muted w-100 text-decoration-none fw-bold" onclick="document.getElementById('modalRetiro').style.display='none'">Cancelar</button></div></div>
        <div id="modalMasivo" class="modal-bg"><div class="box-white p-4"><h5 class="fw-bold text-primary mb-4"><i class="bi bi-lightning-fill text-warning"></i> EDICIÓN MÚLTIPLE</h5><label class="small text-muted fw-bold d-block text-start ps-2 mb-1">Nuevo Precio Gral.</label><input type="number" id="masivo-pre" class="form-control rounded-pill mb-3 text-center fs-5 text-primary fw-bold bg-light border-0" placeholder="$"><label class="small text-muted fw-bold d-block text-start ps-2 mb-1">Nuevo Stock Gral.</label><input type="number" id="masivo-stock" class="form-control rounded-pill mb-4 text-center fs-5 text-success fw-bold bg-light border-0" placeholder="Unidades"><button class="btn btn-primary w-100 fw-bold py-3 rounded-pill shadow-sm mb-2" onclick="guardarMasivo()">APLICAR CAMBIOS</button><button class="btn btn-link text-muted w-100 text-decoration-none fw-bold" onclick="document.getElementById('modalMasivo').style.display='none'">Cancelar</button></div></div>
        <div id="modalIndividual" class="modal-bg"><div class="box-white text-start p-4" style="margin-top: 5vh; margin-bottom: 5vh; max-width: 500px;"><h5 class="fw-bold text-primary text-center mb-4"><i class="bi bi-pencil-square"></i> EDITAR ARTÍCULO</h5><input type="text" id="ind-cod" class="form-control rounded-pill mb-3 bg-light text-muted border-0 text-center fw-bold" readonly><label class="small fw-bold text-muted ps-2">Descripción</label><input type="text" id="ind-desc" class="form-control rounded-pill px-3 mb-3 fw-bold text-dark border-secondary border-opacity-25" autocomplete="off"><label class="small fw-bold text-muted ps-2"><i class="bi bi-camera text-primary"></i> Cambiar Foto</label><input type="file" id="ind-foto" class="form-control rounded-pill px-3 mb-4 bg-light border-0" accept="image/*"><div class="row g-3 mb-4"><div class="col-4"><label class="small fw-bold text-muted ps-2">Precio 1 $</label><input type="number" id="ind-pre" class="form-control rounded-pill text-primary fw-bold px-2 text-center border-primary border-opacity-50"></div><div class="col-4"><label class="small fw-bold text-muted ps-2">Costo $</label><input type="number" id="ind-costo" class="form-control rounded-pill px-2 text-center bg-light border-0"></div><div class="col-4"><label class="small fw-bold text-muted ps-2">Stock</label><input type="number" id="ind-stock" class="form-control rounded-pill text-success fw-bold px-2 text-center border-success border-opacity-50"></div><div class="col-6"><label class="small fw-bold text-muted ps-2">IVA (%)</label><input type="number" id="ind-iva" class="form-control rounded-pill text-center bg-light border-0"></div><div class="col-6"><label class="small fw-bold text-muted ps-2">Unidad</label><select id="ind-unidad" class="form-select rounded-pill text-center bg-light border-0"><option value="PZ">PZ</option><option value="KG">KG</option><option value="LT">LT</option><option value="MT">MT</option><option value="SRV">SRV</option></select></div><div class="col-12 mt-2 border-top pt-2"><h6 class="fw-bold text-secondary small mb-1"><i class="bi bi-tags-fill text-primary"></i> Mayoreo y Especial</h6></div><div class="col-6"><label class="small fw-bold text-muted ps-2">Precio 2 $</label><input type="number" id="ind-p2" class="form-control rounded-pill px-2 text-center bg-light border-0"></div><div class="col-6"><label class="small fw-bold text-muted ps-2">A partir de</label><input type="number" id="ind-cp2" class="form-control rounded-pill px-2 text-center bg-light border-0"></div><div class="col-6"><label class="small fw-bold text-muted ps-2">Precio 3 $</label><input type="number" id="ind-p3" class="form-control rounded-pill px-2 text-center bg-light border-0"></div><div class="col-6"><label class="small fw-bold text-muted ps-2">A partir de</label><input type="number" id="ind-cp3" class="form-control rounded-pill px-2 text-center bg-light border-0"></div><div class="col-12"><label class="small fw-bold text-warning ps-2">Precio Especial $</label><input type="number" id="ind-pe" class="form-control rounded-pill px-2 text-center border-warning border-opacity-50"></div></div><button class="btn btn-primary w-100 fw-bold mb-2 py-3 rounded-pill shadow-sm" onclick="guardarIndividual()">GUARDAR CAMBIOS</button><button class="btn btn-light text-danger w-100 fw-bold mb-2 py-2 rounded-pill border border-danger border-opacity-25" onclick="borrarProductoDefinitivo(document.getElementById('ind-cod').value)"><i class="bi bi-trash"></i> ELIMINAR</button><button class="btn btn-link text-muted w-100 text-center text-decoration-none fw-bold" onclick="document.getElementById('modalIndividual').style.display='none'">Cancelar</button></div></div>
        
        <div id="modalTemporal" class="modal-bg"><div class="box-white p-4"><div class="bg-primary bg-opacity-10 text-primary rounded-circle d-flex justify-content-center align-items-center mx-auto mb-3" style="width:50px; height:50px;"><i class="bi bi-plus-lg fs-2"></i></div><h5 class="fw-bold text-dark mb-4">SERVICIO / VENTA LIBRE</h5><input type="text" id="temp-desc" class="form-control rounded-pill px-3 bg-light border-0 mb-3" placeholder="Descripción (Ej. Copias)" autocomplete="off"><input type="number" id="temp-pre" class="form-control rounded-pill px-3 mb-4 text-center fs-3 fw-bold border-primary border-opacity-50 shadow-sm text-primary" placeholder="$ 0.00"><button class="btn btn-primary w-100 fw-bold py-3 rounded-pill shadow-sm mb-2" onclick="agregarTemporal()">AGREGAR AL TICKET</button><button class="btn btn-link text-muted w-100 text-decoration-none fw-bold" onclick="cerrarTemporal()">Cancelar</button></div></div>
        <div id="modalTicket" class="modal-bg"><div class="box-white p-4"><div class="bg-success text-white rounded-circle d-flex justify-content-center align-items-center mx-auto mb-3 shadow" style="width:60px; height:60px;"><i class="bi bi-check-lg fs-1"></i></div><h4 id="ticket-titulo" class="fw-bold text-dark mb-1">¡COBRO EXITOSO!</h4><div class="text-muted small mb-4">Muestra el QR o envía nota al cliente</div><div id="qrcode" class="d-flex justify-content-center mb-4 bg-white p-3 rounded-4 border shadow-sm mx-auto" style="width: fit-content;"></div><button class="btn btn-primary w-100 fw-bold shadow-sm rounded-pill mb-2 py-3" onclick="imprimirTicketFisico()">🖨️ IMPRIMIR TICKET</button><a id="btn-wa-directo" href="#" target="_blank" class="btn btn-success w-100 fw-bold mb-3 py-3 rounded-pill shadow-sm" style="background-color: #25D366; border: none; display: none;"><i class="bi bi-whatsapp fs-5 me-2"></i> ENVIAR TICKET</a><h3 class="text-primary fw-bold mb-4" id="ticket-total"></h3><button class="btn btn-dark w-100 fw-bold py-3 rounded-pill shadow-sm" onclick="location.reload()">NUEVA OPERACIÓN (ESC)</button></div></div>
        <div id="modalDetalle" class="modal-bg"><div class="box-white p-4"><h5 id="detalle-titulo" class="fw-bold text-dark mb-3">DETALLE DE NOTA</h5><div id="cont-detalle" class="text-start mb-4 small bg-light rounded-4 p-3 border border-light" style="max-height: 50vh; overflow-y: auto;"></div><div id="area-liquidar"></div><button class="btn btn-light w-100 mt-3 fw-bold rounded-pill text-secondary border" onclick="cerrarDetalle()">Cerrar</button></div></div>

        <!-- BARRA FLOTANTE DE COBRO (FOOTER) -->
        <div id="footer-mini" class="footer-cobro" style="display:none; border-radius: 24px 24px 0 0;">
            <div class="d-flex justify-content-between align-items-center max-w-500 mx-auto">
                <div><small class="fw-bold text-muted d-block mb-1" style="letter-spacing: 0.5px;">TOTAL DE VENTA:</small><h1 class="fw-bold text-dark m-0" id="total-mini" style="font-size: 2.2rem; letter-spacing: -1px;">$0.00</h1></div>
                <button class="btn btn-primary fw-bold shadow" style="border-radius: 20px; padding: 16px 35px; font-size: 1.1rem; background: linear-gradient(145deg, #0d6efd, #0b5ed7); border: none;" onclick="abrirModalCobro()">COBRAR (F12) <i class="bi bi-arrow-right fs-5 ms-2"></i></button>
            </div>
        </div>

        <div id="modalCobro" style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(15,23,42,0.85); backdrop-filter: blur(5px); display: none; justify-content: center; align-items: flex-end; z-index: 3000; padding-bottom: 20px;">
            <div class="box-white p-4 shadow-lg" style="width: 95%; max-width: 500px; text-align: left; border-radius: 24px; animation: slideUp 0.3s ease-out;">
                <label class="small fw-bold text-muted ps-2 mb-1">MÉTODO DE PAGO</label>
                <select id="metodo-pago" class="form-select rounded-pill px-3 mb-3 fw-bold border-2 border-primary text-primary bg-primary bg-opacity-10" onchange="actualizarInputsCobro()"><option value="EFECTIVO">💵 EFECTIVO</option><option value="TRANSFERENCIA">💳 TRANSFERENCIA / TARJETA</option></select>
                
                <div class="admin-element mb-3 border-top border-light pt-3">
                    <div class="form-check form-switch mb-2 ps-5"><input class="form-check-input ms-n5" type="checkbox" id="chk-anticipo" style="width: 2.5em; height: 1.25em;" onchange="actualizarInputsCobro()"><label class="form-check-label fw-bold text-primary mt-1" for="chk-anticipo">Registrar Anticipo / Deuda</label></div>
                    <select id="tipo-deuda" class="form-select mb-3 bg-warning bg-opacity-10 text-dark fw-bold border-warning border-opacity-50" style="display:none; border-radius: 12px; font-size: 0.85rem;"><option value="CREDITO">🤝 Fiado / Crédito (Se entrega hoy)</option><option value="APARTADO">📦 Apartado (Se entrega al liquidar)</option></select>
                    {CHK_TALLER}
                </div>
                
                <input type="text" id="nombre-cliente" class="form-control rounded-pill px-3 mb-2 bg-light border-0 fw-bold text-dark" placeholder="Nombre del Cliente (Opcional)" list="dl-clientes" autocomplete="off">
                
                <div id="cont-puntos" style="display:none;" class="bg-success bg-opacity-10 border border-success border-opacity-25 p-2 mb-3 rounded-4 px-3">
                    <div class="form-check form-switch mb-0">
                        <input class="form-check-input" type="checkbox" id="chk-usar-puntos" onchange="actualizarInputsCobro()"><label class="form-check-label fw-bold small text-success mt-1" for="chk-usar-puntos">Usar Monedero (Puntos): <span id="lbl-puntos-disp">$0.00</span></label>
                    </div>
                </div>

                <input type="text" id="link-archivo" class="form-control rounded-pill px-3 mb-4 bg-light border-0 text-primary small" placeholder="🔗 Link de Google Drive / Archivos (Opcional)">
                
                <!-- ✂️ DESCUENTO MANUAL -->
                <div class="mb-3 px-2 d-flex justify-content-between align-items-center">
                    <label class="small fw-bold text-danger mb-0"><i class="bi bi-scissors"></i> Descuento Extra $</label>
                    <input type="number" id="descuento-manual" class="form-control form-control-sm rounded-pill text-center text-danger fw-bold border-danger border-opacity-25" style="width: 100px;" value="0" onkeyup="actualizarInputsCobro()">
                </div>

                <div class="row mb-4 bg-light rounded-4 p-3 border border-light mx-0"><div class="col-6 p-0 pe-2 border-end"><span id="lbl-pago" class="fw-bold text-muted small d-block mb-1">RECIBIDO:</span><input type="number" id="pago-cliente" class="form-control fw-bold border-0 bg-white text-center fs-4 rounded-3 shadow-sm text-primary" onkeyup="calcularCambio()" placeholder="$ 0.00"></div><div class="col-6 p-0 ps-3 text-end d-flex flex-column justify-content-center"><span id="lbl-cambio" class="fw-bold text-muted small d-block mb-1">CAMBIO:</span><h2 class="text-danger fw-bold m-0" id="cambio-cliente" style="letter-spacing: -1px;">$0.00</h2></div></div>
                <div class="d-flex justify-content-between align-items-end mb-4 px-2"><div><small class="fw-bold text-muted d-block mb-1">TOTAL A COBRAR</small><h1 class="fw-bold text-dark m-0" id="total-v" style="letter-spacing: -1px;"></h1></div></div>
                <div class="d-flex gap-2 mb-3"><button id="btn-cotizar" class="btn btn-light border fw-bold text-primary rounded-pill shadow-sm py-3" style="width: 35%;" onclick="guardarCotizacion()"><i class="bi bi-file-text"></i> COTIZAR</button><button id="btn-cobrar" class="btn btn-primary fw-bold shadow rounded-pill py-3 fs-6" style="width: 65%; background: linear-gradient(145deg, #0d6efd, #0b5ed7); border: none;" onclick="confirmarCobro()"><i class="bi bi-check-lg me-1"></i> CONFIRMAR (Enter)</button></div>
                <button class="btn btn-link text-muted w-100 text-decoration-none fw-bold" onclick="cerrarModalCobro()">Cancelar y volver (Esc)</button>
            </div>
        </div>

        <script>

function forzarSincronizacion(boton) {
    // Guardamos el contenido original (el icono y el texto)
    let contenidoOriginal = boton.innerHTML;
    
    // Cambiamos el aspecto mientras trabaja
    boton.innerHTML = "⏳ Sincronizando...";
    boton.style.pointerEvents = "none"; // Evita que le den mil clics

    // Llamamos a la ruta que sí limpia los pendientes
    fetch('http://127.0.0.1:8000/matar-pendientes')
        .then(response => {
            // Éxito total
            boton.innerHTML = "✅ ¡Al día!";
            
            // Después de 3 segundos, regresa a su estado normal
            setTimeout(() => { 
                boton.innerHTML = contenidoOriginal;
                boton.style.pointerEvents = "auto";
            }, 3000);
        })
        .catch(error => {
            // Si el servidor de Python está apagado
            boton.innerHTML = "⚠️ Error Red";
            setTimeout(() => { 
                boton.innerHTML = contenidoOriginal;
                boton.style.pointerEvents = "auto";
            }, 3000);
        });

}    
    async function ejecutarCargaMasivaFotos() {
    const res = await fetch('/fotos-masivas', { method: 'POST' });
    const data = await res.json();
    alert(data.msg);
    if(data.ok) location.reload();
}

        // --- FUNCIONES PARA CONVERTIR NÚMEROS A LETRAS ---
            function numeroALetras(monto) {
                let entero = Math.floor(monto);
                let centavos = Math.round((monto - entero) * 100).toString().padStart(2, '0');
                return toText(entero) + " PESOS " + centavos + "/100 M.N.";
            }
            function toText(n) {
                let un = ['','UNO','DOS','TRES','CUATRO','CINCO','SEIS','SIETE','OCHO','NUEVE','DIEZ','ONCE','DOCE','TRECE','CATORCE','QUINCE','DIECISEIS','DIECISIETE','DIECIOCHO','DIECINUEVE','VEINTE','VEINTIUNO','VEINTIDOS','VEINTITRES','VEINTICUATRO','VEINTICINCO','VEINTISEIS','VEINTISIETE','VEINTIOCHO','VEINTINUEVE'];
                let dec = ['','DIEZ','VEINTE','TREINTA','CUARENTA','CINCUENTA','SESENTA','SETENTA','OCHENTA','NOVENTA'];
                let cen = ['','CIENTO','DOSCIENTOS','TRESCIENTOS','CUATROCIENTOS','QUINIENTOS','SEISCIENTOS','SETECIENTOS','OCHOCIENTOS','NOVECIENTOS'];
                if (n===0) return 'CERO'; if (n<30) return un[n];
                if (n<100) return dec[Math.floor(n/10)] + (n%10===0 ? '' : ' Y ' + un[n%10]);
                if (n===100) return 'CIEN';
                if (n<1000) return cen[Math.floor(n/100)] + (n%100===0 ? '' : ' ' + toText(n%100));
                if (n===1000) return 'MIL';
                if (n<1000000) return (n<2000 ? 'MIL' : toText(Math.floor(n/1000)) + ' MIL') + (n%1000===0 ? '' : ' ' + toText(n%1000));
                return 'UN MILLON'; 
            }
                let carrito = []; let totalActual = 0; let qrcodeGen = new QRCode(document.getElementById("qrcode"), { width: 180, height: 180, colorDark : "#1e293b", colorLight : "#ffffff" });
                async function guardarConfigSistem() {
                const datos = {
                    razon_social: document.getElementById('cfg-razon').value,
                    rfc_empresa: document.getElementById('cfg-rfc').value,
                    direccion_empresa: document.getElementById('cfg-dir').value,
                    telefono_empresa: document.getElementById('cfg-tel').value,
                    mensaje_ticket: document.getElementById('cfg-msg').value
                };
                const res = await fetch('/guardar-config-ticket', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(datos)
                });
                if(res.ok) alert("✅ ¡Datos de la empresa guardados correctamente!");
            }
           
     function imprimirTicketFisico() {
                let datosParaImprimir = window.ultimaVentaDatos || {
                    // --- NUEVO: Buscamos si hay un logo configurado ---
                    logo: (document.getElementById('cfg-logo') && document.getElementById('cfg-logo').value) ? document.getElementById('cfg-logo').value : "",
                    
                    razon: (document.getElementById('cfg-razon') && document.getElementById('cfg-razon').value) ? document.getElementById('cfg-razon').value : nombreComercial,
                    rfc: (document.getElementById('cfg-rfc') && document.getElementById('cfg-rfc').value) ? document.getElementById('cfg-rfc').value : "RFC: GENERICO",
                    dir: (document.getElementById('cfg-dir') && document.getElementById('cfg-dir').value) ? document.getElementById('cfg-dir').value : "Dirección no configurada",
                    tel: (document.getElementById('cfg-tel') && document.getElementById('cfg-tel').value) ? document.getElementById('cfg-tel').value : "Tel: ---",
                    msj: (document.getElementById('cfg-msg') && document.getElementById('cfg-msg').value) ? document.getElementById('cfg-msg').value : "¡Gracias por su preferencia!",
                    items: carrito,
                    total: totalActual,
                    pago: parseFloat(document.getElementById('pago-cliente').value) || totalActual,
                    folio: "Venta Actual"
                };

                if (datosParaImprimir.items.length === 0) {
                    alert("⚠️ No hay productos para imprimir.");
                    return;
                }

                let divImpresion = document.createElement('div');
                divImpresion.id = 'area-impresion';
                divImpresion.style.width = '80mm';
                
                let esCotizacion = String(datosParaImprimir.folio).toUpperCase().includes("COT");
                let tituloDocumento = esCotizacion ? "COTIZACIÓN" : "TICKET DE COMPRA";

                // --- NUEVO: Construimos el HTML del logo solo si existe uno ---
                // Le ponemos un ancho máximo de 45mm para que no se desborde y lo forzamos a blanco y negro
                let urlLogoSegura = datosParaImprimir.logo || (document.getElementById('cfg-logo') ? document.getElementById('cfg-logo').value : "");
let logoHtml = urlLogoSegura ? `<img src="${urlLogoSegura}" style="max-width: 45mm; margin-bottom: 10px; filter: grayscale(100%);"><br>` : "";

                // --- Inyectamos el 'logoHtml' justo antes de la 'razon' (nombre de la empresa) ---
                let htmlStr = `<div style="text-align:center; font-family:monospace; color:black; font-size: 14px; width: 100%; margin: 0 auto; padding-top: 25px;">
                    ${logoHtml}
                    <b style="font-size:18px;">${datosParaImprimir.razon}</b><br>${datosParaImprimir.rfc}<br>${datosParaImprimir.dir}<br>${datosParaImprimir.tel}<br>
                    --------------------------------<br><b>${tituloDocumento}</b><br>Folio: #${datosParaImprimir.folio}<br>--------------------------------<br></div>`;
                    
                datosParaImprimir.items.forEach(i => {
                    let nombreProd = i.desc || i.descripcion;
                    let cantidad = i.cant || i.cantidad;
                    let precioTotal = i.pre ? (i.pre * i.cant) : parseFloat(i.total_cobrado);
                    
                    htmlStr += `<div style="font-family:monospace; color:black; font-size: 14px; margin-bottom:4px;">
                        ${cantidad}x ${nombreProd}<br><div style="text-align:right; font-weight:bold;">$${precioTotal.toFixed(2)}</div></div>`;
                });
                
                let cambio = datosParaImprimir.pago - datosParaImprimir.total;
                if(cambio < 0) cambio = 0;
                
                let mensajeFinal = esCotizacion ? "Cotización válida por 15 días." : datosParaImprimir.msj;
                    
                htmlStr += `<div style="text-align:right; font-family:monospace; color:black; font-size: 14px; margin-top:5px; border-top:1px dashed #000; padding-top:5px;">
                    <b style="font-size:16px;">TOTAL: $${datosParaImprimir.total.toFixed(2)}</b><br>
                    <small style="font-size:11px;">(${numeroALetras(datosParaImprimir.total)})</small><br><br>
                    Efectivo: $${datosParaImprimir.pago.toFixed(2)}<br>
                    Cambio: $${cambio.toFixed(2)}<br>
                    --------------------------------<br>
                    <div style="text-align:center; margin-top:10px; font-weight:bold;">${mensajeFinal}</div></div>`;
                
                divImpresion.innerHTML = htmlStr;
                document.body.appendChild(divImpresion);

                // ... (El resto del código de los estilos y window.print() se queda exactamente igual) ...
                let estiloPrint = document.createElement('style');
                estiloPrint.innerHTML = `@media print { body * { visibility: hidden !important; } #area-impresion, #area-impresion * { visibility: visible !important; line-height: 1.1 !important; } #area-impresion { position: absolute; left: 50% !important; top: 0; transform: translateX(-50%) !important; width: 75mm !important; } @page { margin: 0; } }`;
                document.head.appendChild(estiloPrint);

                // Pequeño truco: damos 200 milisegundos para que la imagen cargue antes de lanzar la impresión
                setTimeout(() => {
                    window.print();
                    document.body.removeChild(divImpresion);
                    document.head.removeChild(estiloPrint);
                    window.ultimaVentaDatos = null;
                }, 200);
            }

            const confCaducidad = "{USA_CADUCIDAD}" === "1";
            let nombreComercial = "{EMPRESA_MOSTRADA}"; let rolUsuario = "{USER_ROLE}"; let nombreCajero = "{USER_NAME}";
            let clientesCache = []; let comprasFaltantes = []; let promocionesCache = [];
            let indiceSeleccionado = -1; let indiceCarritoSel = -1;
            window.puntosClienteActual = 0; window.puntosAplicadosReal = 0;
            
            // --- TEMAS (SKINS) ---
            let temaActual = 0;
           const temasVarios = [
                "", // 0: Clásico
                "body, .bg-light, .bg-white { background-color: #121212 !important; color: #e0e0e0 !important; } .header-pro, .footer-cobro, .nav-buttons { background-color: #1e1e1e !important; border-color: #333 !important; } .card-pro, .box-white, .cart-item-card { background-color: #1e1e1e !important; border: 1px solid #333 !important; box-shadow: none !important; } input, select, .form-control { background-color: #2b2b2b !important; border: 1px solid #444 !important; color: #fff !important; } .text-dark { color: #fff !important; } .modal-bg { background: rgba(0,0,0,0.85); }",
                // 1: Oscuro
                "body, .bg-light, .bg-white { background-color: #0f172a !important; color: #f8fafc !important; } .header-pro, .footer-cobro, .nav-buttons { background-color: #1e293b !important; border-color: #334155 !important; } .card-pro, .box-white, .cart-item-card { background-color: #1e293b !important; border: 1px solid #334155 !important; } input, select, .form-control { background-color: #334155 !important; border: 1px solid #475569 !important; color: #fff !important; } .text-dark { color: #f1f5f9 !important; }",
                // 2: Azul
                "body, .bg-light, .bg-white { background-color: #000 !important; color: #00ff00 !important; font-family: monospace !important; } .card-pro, .box-white { border: 1px solid #00ff00 !important; background: #000 !important; } .text-dark, .text-primary { color: #00ff00 !important; } .btn-primary { background: #004400 !important; border: 1px solid #00ff00 !important; }",
                // 3: Hacker
                "body { background-color: #f8f9fa !important; } .header-pro { border-bottom: 3px solid #00aeef !important; } .nav-buttons { border-bottom: 3px solid #ec008c !important; } .footer-cobro { border-top: 3px solid #fff200 !important; } .text-primary { color: #ec008c !important; }",
                // 4: CMYK
                "body, .bg-light, .bg-white { background-color: #09090b !important; color: #e2e8f0 !important; } .card-pro, .box-white { background-color: #0f172a !important; border: 1px solid #3b0764 !important; } .btn-primary { background: linear-gradient(145deg, #7c3aed, #4f46e5) !important; }",
                // 5: Neón
                "body { background-color: #fdf8f5 !important; color: #4a3b32 !important; } .card-pro { background-color: #ffffff !important; border: 1px solid #e6d5c9 !important; } .btn-primary { background-color: #795548 !important; }",
                // 6: Café
                "body { background-color: #300a24 !important; color: #ffffff !important; } .header-pro, .nav-buttons, .footer-cobro { background-color: #2c001e !important; border-color: #aea79f !important; } .card-pro, .box-white, .cart-item-card { background-color: #ffffff !important; color: #333 !important; border-radius: 6px !important; border: none !important; } .btn-primary { background-color: #e95420 !important; border: none !important; border-radius: 4px !important; } .nav-btn.active { background-color: #e95420 !important; color: white !important; }",                            
                // 7: LINUX UBUNTU (Remplaza al psicodélico)
                "body { background: linear-gradient(135deg, #8a9198, #d4d7d9, #8a9198) !important; } .card-pro { background: linear-gradient(to bottom, #ffffff, #e4e5e6) !important; border: 1px solid #9c9c9c !important; }", 
                // 8: Metálico
                "body { background-color: #ece9d8 !important; } .header-pro { background: linear-gradient(to bottom, #0058e6, #288eff) !important; } .card-pro { border: 1px solid #0054e3 !important; border-top: 20px solid #0058e6 !important; }",
                // 9: Windows XP
        "body { background-color: #f5f5f7 !important; } .header-primary { background-color: #0033cc !important; }",
        
        // 10: Mac OS
        "body { background-color: #e5e5e5 !important; color: #000 !important; }",

        // 11: PREMIUM DARK (Negro Absoluto y Amarillo Brillante)
        "body, html, .container-fluid, .bg-light, .bg-white, .card, .modal-content { background-color: #0a0c10 !important; color: #f3f4f6 !important; } .navbar, .bg-primary, .bg-dark { background-color: #13161c !important; border-bottom: 1px solid #2b303b !important; } table, .table, th, td { background-color: transparent !important; color: #f3f4f6 !important; border-color: #2b303b !important; } thead th, .table-dark th { border-bottom: 2px solid #facc15 !important; color: #facc15 !important; text-transform: uppercase; } .btn-primary, .btn-success, .btn-info, .btn-dark { background-color: #facc15 !important; color: #000 !important; border: none !important; font-weight: 800 !important; box-shadow: 0 0 15px rgba(250, 204, 21, 0.3) !important; } .text-dark, .text-muted { color: #9ca3af !important; } input, select, .form-control, .form-select { background-color: #16191f !important; color: #facc15 !important; border: 1px solid #333 !important; } input:focus { box-shadow: 0 0 10px rgba(250, 204, 21, 0.5) !important; border-color: #facc15 !important; }"
];

            function aplicarTemaManual(idx) {
                document.getElementById('theme-style').innerHTML = temasVarios[idx];
            }

            function cambiarTema() { temaActual++; if(temaActual >= temasVarios.length) temaActual = 0; document.getElementById('theme-style').innerHTML = temasVarios[temaActual]; }

            let sincronizando = false;
            async function autoSincronizacion() { if (sincronizando) return; sincronizando = true; try { await fetch('/sincronizar-buzon', {method: 'POST'}); } catch(e) {} sincronizando = false; }
            async function sincronizarBuzonClick() { const btn = document.getElementById('btn-sync'); btn.innerHTML = '<i class="bi bi-arrow-repeat spin"></i> Sync...'; btn.disabled = true; try { const res = await fetch('/sincronizar-buzon', {method: 'POST'}); const data = await res.json(); alert("☁️ " + data.msg); } catch(e) { alert("Error de conexión."); } btn.innerHTML = '<i class="bi bi-cloud-arrow-up text-primary"></i> Sincronizar'; btn.disabled = false; }

            document.addEventListener("DOMContentLoaded", function() {
                let hoy = new Date().toISOString().split('T')[0];
                if(document.getElementById('rep-inicio')) document.getElementById('rep-inicio').value = hoy;
                if(document.getElementById('rep-fin')) document.getElementById('rep-fin').value = hoy;
                if(document.getElementById('np-fecha')) document.getElementById('np-fecha').value = hoy; 
                if(document.getElementById('promo-inicio')) document.getElementById('promo-inicio').value = hoy;
                if(document.getElementById('promo-fin')) { let fechaFin = new Date(); fechaFin.setDate(fechaFin.getDate() + 10); document.getElementById('promo-fin').value = fechaFin.toISOString().split('T')[0]; }
                if (confCaducidad) { let cc = document.getElementById('cont-caducidad'); if(cc) cc.style.display = 'block'; }
                cargarDirectorioCRM(); cargarPromociones(); setInterval(autoSincronizacion, 30000); 

                let txtCliente = document.getElementById('nombre-cliente');
                if(txtCliente) {
                    txtCliente.addEventListener('input', function() {
                        let cli = clientesCache.find(c => c.nombre.toLowerCase() === this.value.trim().toLowerCase());
                        if(cli && parseFloat(cli.puntos) > 0) { document.getElementById('cont-puntos').style.display = 'block'; document.getElementById('lbl-puntos-disp').innerText = '$' + parseFloat(cli.puntos).toFixed(2); window.puntosClienteActual = parseFloat(cli.puntos); } else { document.getElementById('cont-puntos').style.display = 'none'; let chk = document.getElementById('chk-usar-puntos'); if(chk) chk.checked = false; window.puntosClienteActual = 0; }
                        actualizarInputsCobro();
                    });
                }
                function habilitarTeclado(inputId, resId, esVenta) {
                    let inputEl = document.getElementById(inputId); if(!inputEl) return; let idxSel = -1;
                    inputEl.addEventListener('keydown', async function(e) {
                        let items = document.querySelectorAll('#' + resId + ' .card-pro');
                        if(e.key === 'ArrowDown') { e.preventDefault(); if(items.length > 0) { idxSel++; if(idxSel >= items.length) idxSel = 0; resaltar(items, idxSel); } }
                        else if(e.key === 'ArrowUp') { e.preventDefault(); if(items.length > 0) { idxSel--; if(idxSel < 0) idxSel = items.length - 1; resaltar(items, idxSel); } }
                        else if(e.key === 'Enter') { e.preventDefault(); if(items.length > 0 && idxSel >= 0) { clickearItem(items[idxSel]); idxSel = -1; } else if(items.length > 0 && idxSel === -1) { clickearItem(items[0]); idxSel = -1; } else if (esVenta) { let val = this.value.trim(); if(val) { const res = await fetch('/buscar?q=' + encodeURIComponent(val)); const productos = await res.json(); let prod = productos.find(p => p.CodigoProducto.toLowerCase() === val.toLowerCase()); if(prod) { agregarAlCarrito(prod.CodigoProducto, prod.Descripcion, parseFloat(prod.Precio||0), parseFloat(prod.Existencia||0), prod.Unidad || 'PZ', parseFloat(prod.Precio_2||0), parseFloat(prod.Cant_P2||0), parseFloat(prod.Precio_3||0), parseFloat(prod.Cant_P3||0), parseFloat(prod.Precio_Especial||0)); this.value = ''; document.getElementById(resId).innerHTML = ''; } } } }
                    });
                    inputEl.addEventListener('input', function() { idxSel = -1; });
                }
                habilitarTeclado('bus-v', 'res-v', true); habilitarTeclado('promo-cod', 'res-promo', false); habilitarTeclado('bus-ajustes', 'res-ajustes', false); habilitarTeclado('bus-c', 'res-c', false);             
            }); 
            
            function resaltar(items, idx) { items.forEach((item, i) => { if(i === idx) { item.style.border = '2px solid #0d6efd'; item.style.boxShadow = '0 8px 20px rgba(13,110,253,0.1)'; item.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); } else { item.style.border = 'none'; item.style.boxShadow = '0 4px 15px rgba(0,0,0,0.04)'; } }); }
            function clickearItem(item) { let btn = item.querySelector('button'); if(btn) { btn.click(); } else { let clic = item.querySelector('.flex-grow-1'); if(clic) clic.click(); } }

            window.addEventListener('keydown', function(e) { 
                if(['F2', 'F3', 'F6', 'F12'].includes(e.key)) { e.preventDefault(); }
                if (indiceCarritoSel >= 0) {
                    if (e.key === 'ArrowDown') { e.preventDefault(); indiceCarritoSel++; if(indiceCarritoSel >= carrito.length) indiceCarritoSel = 0; actualizarVistaCarrito(); return; }
                    if (e.key === 'ArrowUp') { e.preventDefault(); indiceCarritoSel--; if(indiceCarritoSel < 0) indiceCarritoSel = carrito.length - 1; actualizarVistaCarrito(); return; }
                    if (e.key === 'Delete' || e.key === 'Backspace') { e.preventDefault(); eliminarDelCarrito(indiceCarritoSel); return; }
                    if (e.key === 'Escape' || e.key === 'F2') { indiceCarritoSel = -1; actualizarVistaCarrito(); let b = document.getElementById('bus-v'); if(b) b.focus(); if(e.key === 'Escape') return; }
                }
                if (e.key === 'F3') { if(document.getElementById('tab-venta').style.display !== 'none' && carrito.length > 0) { indiceCarritoSel = 0; actualizarVistaCarrito(); return; } }
                if (e.key === 'Escape') { if(document.getElementById('modalCobro').style.display === 'flex') { cerrarModalCobro(); } else { location.reload(); } } 
                if (e.key === 'F6') abrirTemporal(); 
                if (e.key === 'F2') { indiceCarritoSel = -1; actualizarVistaCarrito(); switchTab('venta'); setTimeout(() => document.getElementById('bus-v').focus(), 100); }
                if (e.key === 'F12') { if(carrito.length > 0) { abrirModalCobro(); } else { let b = document.getElementById('bus-v'); if(b) { b.style.borderColor = '#ef4444 !important'; setTimeout(()=> b.style.borderColor = '#e2e8f0 !important', 500); } } }
                if (e.key === 'Enter' && document.getElementById('modalCobro').style.display === 'flex') { e.preventDefault(); confirmarCobro(); }
            });

            function calcularUtilidad() { let c = parseFloat(document.getElementById('np-costo').value)||0; let p = parseFloat(document.getElementById('np-pre').value)||0; let u = p - c; let por = c > 0 ? (u/c)*100 : 100; document.getElementById('lbl-utilidad').innerText = `Ganancia: $${u.toFixed(2)} (${por.toFixed(0)}%)`; }

            function switchTab(tab){
                document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
                let btnTarget = document.getElementById('btn-' + tab); if (btnTarget) btnTarget.classList.add('active');
                ['venta', 'ofertas', 'excel', 'clientes', 'taller', 'dtf', 'cotizaciones', 'pendientes', 'historial', 'consultas', 'inventario', 'reportes', 'usuarios', 'ajustes', 'config-sistem'].forEach(t => { let el=document.getElementById('tab-' + t); if(el) el.style.display = 'none'; });
                let tabTarget = document.getElementById('tab-' + tab); if (tabTarget) tabTarget.style.display = 'block';
                if(tab !== 'venta') { document.getElementById('footer-mini').style.display = 'none'; } else { actualizarVistaCarrito(); }
                
                if(document.getElementById('bus-v')) { document.getElementById('bus-v').value = ''; document.getElementById('res-v').innerHTML = ''; }
                if(document.getElementById('bus-c')) { document.getElementById('bus-c').value = ''; document.getElementById('res-c').innerHTML = ''; }
                if(document.getElementById('bus-ajustes')) { document.getElementById('bus-ajustes').value = ''; document.getElementById('res-ajustes').innerHTML = ''; document.getElementById('barra-masiva').style.display = 'none'; }
                if(document.getElementById('promo-cod')) { document.getElementById('promo-cod').value = ''; document.getElementById('res-promo').innerHTML = ''; document.getElementById('promo-desc-lbl').innerText = ''; }
                if(document.getElementById('np-cod')) { document.getElementById('np-cod').value = ''; document.getElementById('np-desc').value = ''; document.getElementById('np-pre').value = ''; document.getElementById('np-foto').value = ''; document.getElementById('np-unidad').value = 'PZ'; document.getElementById('np-costo').value = '0'; document.getElementById('np-stock').value = '0'; document.getElementById('np-p2').value = ''; document.getElementById('np-cp2').value = ''; document.getElementById('np-p3').value = ''; document.getElementById('np-cp3').value = ''; document.getElementById('np-pe').value = ''; document.getElementById('lbl-utilidad').innerText='Ganancia: --'; }
                
                setTimeout(() => { if(tab === 'venta') { let b = document.getElementById('bus-v'); if(b) b.focus(); } else if(tab === 'consultas') { let b = document.getElementById('bus-c'); if(b) b.focus(); } else if(tab === 'ajustes') { let b = document.getElementById('bus-ajustes'); if(b) b.focus(); } else if(tab === 'ofertas') { let b = document.getElementById('promo-cod'); if(b) b.focus(); } else if(tab === 'inventario') { let b = document.getElementById('np-cod'); if(b) b.focus(); } }, 100);
                if(tab === 'clientes') cargarDirectorioCRM(); if(tab === 'taller') cargarTaller(); if(tab === 'cotizaciones') cargarCotizaciones(); if(tab === 'reportes') { cargarReportes(); cargarMiTurno(); cargarComboCajeros(); } if(tab === 'pendientes') cargarPendientes(); if(tab === 'historial') cargarHistorial(); if(tab === 'ofertas') cargarPromociones(); if(tab === 'usuarios') cargarUsuarios(); 
            }

            function calcularDTF() {
                let aFilm = parseFloat(document.getElementById('dtf-ancho-film').value) || 60; let cFilm = parseFloat(document.getElementById('dtf-costo-film').value) || 0; let cTinta = parseFloat(document.getElementById('dtf-costo-tinta').value) || 0; let cPolvo = parseFloat(document.getElementById('dtf-costo-polvo').value) || 0;
                let aDis = parseFloat(document.getElementById('dtf-ancho-cliente').value) || 0; let lDis = parseFloat(document.getElementById('dtf-largo-cliente').value) || 0; let margen = parseFloat(document.getElementById('dtf-margen').value) || 0;
                let area_total = aDis * lDis; let costo_cm2_film = cFilm / (aFilm * 100); let costo_film_diseno = area_total * costo_cm2_film;
                let costo_ml_tinta = cTinta / 1000; let costo_tinta_diseno = area_total * (0.0012) * costo_ml_tinta;
                let costo_g_polvo = cPolvo / 1000; let costo_polvo_diseno = area_total * (0.0015) * costo_g_polvo;
                let costo_base = costo_film_diseno + costo_tinta_diseno + costo_polvo_diseno; let precio_sugerido = costo_base * (1 + (margen / 100));
                document.getElementById('dtf-res-costo').innerText = '$' + costo_base.toFixed(2); document.getElementById('dtf-res-venta').innerText = '$' + precio_sugerido.toFixed(2);
            }
            function agregarAlTicketDTF() {
                let precio = parseFloat(document.getElementById('dtf-res-venta').innerText.replace('$', '')); let aDis = document.getElementById('dtf-ancho-cliente').value; let lDis = document.getElementById('dtf-largo-cliente').value;
                if (precio <= 0 || !aDis || !lDis) { alert("⚠️ Ingresa las medidas del cliente para calcular primero."); return; }
                let desc = `Impresión DTF (${aDis}cm x ${lDis}cm)`; carrito.push({cod: 'SRV-DTF', desc: desc, pre: precio, stock: '-', cant: 1, unidad: 'SRV', p2:0, cp2:0, p3:0, cp3:0, pe:0});
                document.getElementById('dtf-ancho-cliente').value = ''; document.getElementById('dtf-largo-cliente').value = ''; document.getElementById('dtf-res-costo').innerText = '$0.00'; document.getElementById('dtf-res-venta').innerText = '$0.00';
                switchTab('venta'); actualizarVistaCarrito();
            }

            async function cargarPromociones() { try { const res = await fetch('/lista-promociones'); promocionesCache = await res.json(); const lista = document.getElementById('lista-promociones'); let hoy = new Date().toISOString().split('T')[0]; if (lista) { lista.innerHTML = ''; if (promocionesCache.length === 0) { lista.innerHTML = '<div class="text-center text-muted small mt-3">No hay promociones activas.</div>'; } else { promocionesCache.forEach(p => { let esVigente = (p.fecha_inicio <= hoy && p.fecha_fin >= hoy); let badgeEstado = esVigente ? '<span class="badge bg-success ms-2 rounded-pill">VIGENTE</span>' : '<span class="badge bg-secondary ms-2 rounded-pill">VENCIDA</span>'; let tipoFondo = p.cantidad_requerida === 1 ? 'border-danger' : 'border-warning'; let tipoTexto = p.cantidad_requerida === 1 ? `¡OFERTA! Todo a $${p.precio_promocional.toFixed(2)}` : `COMBO: Lleva ${p.cantidad_requerida} por $${p.precio_promocional.toFixed(2)}`; lista.innerHTML += `<div class="card-pro d-flex justify-content-between align-items-center mb-2 shadow-sm border-start border-4 ${tipoFondo}"><div><div class="fw-bold text-dark fs-6">${tipoTexto} ${badgeEstado}</div><div class="text-muted small">Cód: ${p.codigo_producto}</div><div class="text-danger small" style="font-size: 0.7rem;">Del ${p.fecha_inicio} al ${p.fecha_fin}</div></div><button class="btn btn-sm btn-light text-danger rounded-circle shadow-sm border" style="width:35px;height:35px;" onclick="borrarPromocion(${p.id})"><i class="bi bi-trash-fill"></i></button></div>`; }); } } actualizarVistaCarrito(); } catch(e) {} }
            async function crearPromocion() { const cod = document.getElementById('promo-cod').value.trim(); const cant = parseInt(document.getElementById('promo-cant').value); const precio = parseFloat(document.getElementById('promo-precio').value); const ini = document.getElementById('promo-inicio').value; const fin = document.getElementById('promo-fin').value; if(!cod || isNaN(cant) || isNaN(precio)) { alert("Faltan datos."); return; } const res = await fetch('/nueva-promocion', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({codigo: cod, cant: cant, precio: precio, inicio: ini, fin: fin}) }); if(res.ok) { alert("¡Promoción activada localmente!"); document.getElementById('promo-cod').value = ''; document.getElementById('promo-desc-lbl').innerText = ''; document.getElementById('res-promo').innerHTML = ''; cargarPromociones(); } else { const data = await res.json(); alert(data.msg); } }
            async function borrarPromocion(id) { if(confirm('¿Desactivar y borrar?')) { await fetch('/borrar-promocion/' + id, { method: 'POST' }); cargarPromociones(); } }

            let html5QrcodeScanner = null;
            function iniciarEscaneo(modo) {
                document.getElementById('stop-scan').style.display = 'block'; document.getElementById('reader').style.display = 'block';
                if (!html5QrcodeScanner) { html5QrcodeScanner = new Html5QrcodeScanner("reader", { fps: 10, qrbox: {width: 250, height: 80} }, false); }
                html5QrcodeScanner.render((texto_escaneado) => { detenerEscaneo(); if(modo === 'venta') { document.getElementById('bus-v').value = texto_escaneado; ejecutarBusqueda(texto_escaneado, 'res-v', 'venta'); } else if(modo === 'consulta') { document.getElementById('bus-c').value = texto_escaneado; ejecutarBusqueda(texto_escaneado, 'res-c', 'consulta'); } else if(modo === 'entrada') { document.getElementById('np-cod').value = texto_escaneado; verificarCodigoEntrada(texto_escaneado); } else if(modo === 'ajustes') { document.getElementById('bus-ajustes').value = texto_escaneado; ejecutarBusquedaAjustes(texto_escaneado); } else if(modo === 'promo') { document.getElementById('promo-cod').value = texto_escaneado; ejecutarBusqueda(texto_escaneado, 'res-promo', 'promo'); } }, (error) => {});
            }
            function detenerEscaneo() { if (html5QrcodeScanner) { html5QrcodeScanner.clear(); } document.getElementById('stop-scan').style.display = 'none'; document.getElementById('reader').style.display = 'none'; }

            async function ejecutarBusqueda(q, target, modo){
                const contenedor = document.getElementById(target); if(!q || q.trim().length === 0) { contenedor.innerHTML = ''; if(modo==='promo') document.getElementById('promo-desc-lbl').innerText=''; return; }
                const res = await fetch('/buscar?q=' + encodeURIComponent(q)); const productos = await res.json(); contenedor.innerHTML = '';
                if (modo === 'promo' && productos.length === 1 && productos[0].CodigoProducto === q.trim()) { seleccionarPromo(productos[0].CodigoProducto, productos[0].Descripcion, parseFloat(productos[0].Precio||0)); return; }
                productos.forEach(p => {
                    const pReal = parseFloat(p.Precio || 0); const sReal = p.Existencia || 0; const unidad = p.Unidad || 'PZ'; let badgeColor = sReal > 5 ? 'bg-success' : (sReal > 0 ? 'bg-warning text-dark' : 'bg-danger'); let txtStock = sReal > 5 ? sReal + ' ' + unidad : (sReal > 0 ? '⚠️ ' + sReal + ' ' + unidad : '❌ AGOTADO'); let accion = '';
                    if (modo === 'venta') { accion = '<button class="btn btn-primary fw-bold px-4 rounded-pill shadow-sm" onclick="agregarAlCarrito(\\'' + p.CodigoProducto + '\\',\\'' + p.Descripcion + '\\',' + pReal + ',' + sReal + ', \\'' + unidad + '\\', ' + (p.Precio_2||0) + ', ' + (p.Cant_P2||0) + ', ' + (p.Precio_3||0) + ', ' + (p.Cant_P3||0) + ', ' + (p.Precio_Especial||0) + ')"><i class="bi bi-plus-lg"></i></button>'; } else if (modo === 'consulta') { accion = '<div class="text-end"><span class="badge ' + badgeColor + ' fs-6 px-3 py-2 shadow-sm rounded-pill">' + txtStock + '</span></div>'; } else if (modo === 'promo') { accion = '<button class="btn btn-warning fw-bold px-4 rounded-pill text-dark shadow-sm" onclick="seleccionarPromo(\\'' + p.CodigoProducto + '\\', \\'' + p.Descripcion + '\\', ' + pReal + ')">Elegir</button>'; }
                    let imgHtml = p.imagen ? `<img src="/fotos-locales/${p.imagen}" style="width: 55px; height: 55px; object-fit: cover; background: #fff; border-radius: 12px; margin-right: 15px; border: 1px solid #f1f5f9; box-shadow: 0 2px 5px rgba(0,0,0,0.02);">` : `<div style="width: 55px; height: 55px; background: #f8fafc; border-radius: 12px; margin-right: 15px; display: flex; align-items: center; justify-content: center; color: #cbd5e1; border: 1px solid #f1f5f9;"><i class="bi bi-image fs-4"></i></div>`;
                    contenedor.innerHTML += '<div class="card-pro d-flex justify-content-between align-items-center mb-2 px-3 py-2"><div class="d-flex align-items-center w-75">' + imgHtml + '<div class="small"><b class="fs-6 text-dark" style="letter-spacing: -0.3px;">' + p.Descripcion + '</b><br><span class="precio-txt">$' + pReal.toFixed(2) + '</span><br><small class="text-muted" style="font-size: 0.7rem;">Cód: ' + p.CodigoProducto + '</small></div></div><div>' + accion + '</div></div>';
                }); if(modo === 'promo' && productos.length === 0) { document.getElementById('promo-desc-lbl').innerText = "❌ Producto no encontrado"; document.getElementById('promo-desc-lbl').className = "text-danger fw-bold small mt-1"; }
            }
            function seleccionarPromo(cod, desc, pre) { document.getElementById('promo-cod').value = cod; document.getElementById('promo-desc-lbl').innerText = "✔️ " + desc + " (Precio normal: $" + pre.toFixed(2) + ")"; document.getElementById('promo-desc-lbl').className = "text-success fw-bold small mt-1"; document.getElementById('res-promo').innerHTML = ''; }

            async function verificarCodigoEntrada(val) {
                if (!val || val.trim() === '') return;
                const res = await fetch('/buscar?q=' + encodeURIComponent(val)); const productos = await res.json(); const prod = productos.find(p => p.CodigoProducto.toLowerCase() === val.trim().toLowerCase() || p.Descripcion.toLowerCase() === val.trim().toLowerCase());
                if (prod) { document.getElementById('dup-cod').innerText = prod.CodigoProducto; document.getElementById('dup-desc').innerText = prod.Descripcion; document.getElementById('dup-pre').innerText = '$' + parseFloat(prod.Precio || 0).toFixed(2); document.getElementById('dup-stock').innerText = prod.Existencia || 0; document.getElementById('modalDuplicado').style.display = 'flex'; if (document.getElementById('np-cod').value.toLowerCase() === val.toLowerCase()) { document.getElementById('np-cod').value = ''; } else { document.getElementById('np-desc').value = ''; } }
            }
            function cerrarModalDuplicado() { document.getElementById('modalDuplicado').style.display = 'none'; document.getElementById('np-cod').focus(); }

            async function crearProducto() {
                const cod = document.getElementById('np-cod').value.trim(); const desc = document.getElementById('np-desc').value.trim(); const cat = document.getElementById('np-cat').value.trim(); const fecha = document.getElementById('np-fecha').value; const pre = parseFloat(document.getElementById('np-pre').value) || 0; const costo = parseFloat(document.getElementById('np-costo').value) || 0; const stock = parseFloat(document.getElementById('np-stock').value) || 0; const prov = document.getElementById('np-prov').value.trim(); const wa = document.getElementById('np-wa').value.trim(); const mail = document.getElementById('np-mail').value.trim(); const foto = document.getElementById('np-foto').files[0]; const unidad = document.getElementById('np-unidad').value; const caducidad = document.getElementById('np-caducidad') ? document.getElementById('np-caducidad').value : '';
                const p2 = parseFloat(document.getElementById('np-p2').value) || 0; const cp2 = parseFloat(document.getElementById('np-cp2').value) || 0; const p3 = parseFloat(document.getElementById('np-p3').value) || 0; const cp3 = parseFloat(document.getElementById('np-cp3').value) || 0; const pe = parseFloat(document.getElementById('np-pe').value) || 0;
                if(!cod || !desc) { alert("El Código y la Descripción son obligatorios."); document.getElementById('np-cod').focus(); return; }
                const formData = new FormData(); formData.append('cod', cod); formData.append('desc', desc); formData.append('cat', cat); formData.append('fecha', fecha); formData.append('pre', pre); formData.append('costo', costo); formData.append('stock', stock); formData.append('prov', prov); formData.append('wa', wa); formData.append('mail', mail); formData.append('caducidad', caducidad); formData.append('unidad', unidad); formData.append('p2', p2); formData.append('cp2', cp2); formData.append('p3', p3); formData.append('cp3', cp3); formData.append('pe', pe); if(foto) formData.append('foto', foto);
                const res = await fetch('/nuevo-producto', { method: 'POST', body: formData }); const data = await res.json();
                if(data.ok) { alert('¡Entrada guardada!'); document.getElementById('np-cod').value = ''; document.getElementById('np-desc').value = ''; document.getElementById('np-stock').value = '0'; document.getElementById('np-foto').value = ''; document.getElementById('np-unidad').value = 'PZ'; document.getElementById('np-p2').value = ''; document.getElementById('np-cp2').value = ''; document.getElementById('np-p3').value = ''; document.getElementById('np-cp3').value = ''; document.getElementById('np-pe').value = ''; document.getElementById('lbl-utilidad').innerText='Ganancia: --'; document.getElementById('np-cod').focus(); } else if (data.duplicado) { document.getElementById('dup-cod').innerText = data.prod.CodigoProducto; document.getElementById('dup-desc').innerText = data.prod.Descripcion; document.getElementById('dup-pre').innerText = '$' + parseFloat(data.prod.Precio).toFixed(2); document.getElementById('dup-stock').innerText = data.prod.Existencia; document.getElementById('modalDuplicado').style.display = 'flex'; } else { alert(data.msg); }
            }

            async function generarListaCompras() { const res = await fetch('/lista-compras'); comprasFaltantes = await res.json(); const cont = document.getElementById('lista-compras-content'); cont.innerHTML = ''; if(comprasFaltantes.length === 0) { cont.innerHTML = '<div class="alert alert-success text-center fw-bold rounded-pill"><i class="bi bi-emoji-smile"></i> ¡Inventario sano! No hay urgencias.</div>'; } else { let html = '<ul class="list-group list-group-flush bg-transparent">'; comprasFaltantes.forEach(p => { let prov = p.Proveedor ? p.Proveedor : 'Desconocido'; let wp = p.Prov_WhatsApp ? ` <a href="https://wa.me/${p.Prov_WhatsApp}" target="_blank" class="badge bg-success ms-1 rounded-pill text-decoration-none"><i class="bi bi-whatsapp"></i> Chat</a>` : ''; html += `<li class="list-group-item d-flex justify-content-between align-items-start px-1 bg-transparent border-light"><div class="ms-2 me-auto"><div class="fw-bold text-dark" style="font-size:0.85rem;">${p.Descripcion}</div><small class="text-muted"><i class="bi bi-truck"></i> Prov: ${prov}${wp}</small></div><span class="badge bg-danger rounded-pill shadow-sm">Quedan ${p.Existencia}</span></li>`; }); html += '</ul>'; cont.innerHTML = html; } document.getElementById('modalCompras').style.display = 'flex'; }
            function enviarListaWhatsApp() { if(comprasFaltantes.length === 0) return; let texto = "*📝 MI LISTA DE COMPRAS - URGENTE*\\n\\n"; comprasFaltantes.forEach(p => { texto += '• ' + p.Descripcion + ' (Quedan: ' + p.Existencia + ')\\n'; }); window.open("https://wa.me/?text=" + encodeURIComponent(texto), '_blank'); }
            async function cargarDirectorioCRM() { const res = await fetch('/clientes'); clientesCache = await res.json(); const dl = document.getElementById('dl-clientes'); if(dl) { dl.innerHTML = ''; clientesCache.forEach(c => { dl.innerHTML += '<option value="' + c.nombre + '">'; }); } renderizarListaClientes(clientesCache); }
            function renderizarListaClientes(lista) { const contenedor = document.getElementById('lista-directorio-clientes'); if(!contenedor) return; contenedor.innerHTML = ''; if(lista.length === 0) { contenedor.innerHTML = '<div class="text-center text-muted small mt-3">No hay clientes registrados.</div>'; return; } lista.forEach(c => { let badgePts = parseFloat(c.puntos) > 0 ? `<span class="badge bg-success rounded-pill ms-2"><i class="bi bi-gift"></i> $${parseFloat(c.puntos).toFixed(2)} pts</span>` : ''; contenedor.innerHTML += '<div class="card-pro d-flex justify-content-between align-items-center mb-2 px-4 shadow-sm" onclick="abrirFichaCliente(\\'' + c.nombre + '\\')" style="cursor:pointer; border-left: 4px solid #0d6efd;"><div><div class="fw-bold text-dark fs-6">' + c.nombre + badgePts + '</div><div class="text-muted small"><i class="bi bi-whatsapp text-success"></i> ' + (c.telefono || '---') + ' &nbsp;|&nbsp; <i class="bi bi-envelope"></i> ' + (c.correo || '---') + '</div></div><div class="bg-light rounded-circle d-flex align-items-center justify-content-center" style="width:35px;height:35px;"><i class="bi bi-chevron-right text-primary"></i></div></div>'; }); }
            function filtrarClientes(q) { const filtrados = clientesCache.filter(c => c.nombre.toLowerCase().includes(q.toLowerCase()) || (c.telefono && c.telefono.includes(q))); renderizarListaClientes(filtrados); }
            async function crearCliente() { const n = document.getElementById('nc-nombre').value.trim(); const t = document.getElementById('nc-tel').value.trim(); const c = document.getElementById('nc-correo').value.trim(); if(!n) { alert("Nombre obligatorio."); return; } const res = await fetch('/nuevo-cliente', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({nombre: n, tel: t, correo: c}) }); const data = await res.json(); if(data.ok) { document.getElementById('nc-nombre').value = ''; document.getElementById('nc-tel').value = ''; document.getElementById('nc-correo').value = ''; alert("Cliente guardado."); cargarDirectorioCRM(); } else { alert(data.msg); } }
            
            async function abrirFichaCliente(nombre) { const res = await fetch('/historial-cliente?nombre=' + encodeURIComponent(nombre)); const data = await res.json(); let html = '<div class="bg-primary bg-opacity-10 text-primary rounded-circle d-flex justify-content-center align-items-center mx-auto mb-3" style="width:60px; height:60px;"><i class="bi bi-person-badge fs-2"></i></div><h4 class="fw-bold text-dark mb-4 text-center">' + nombre + '</h4>'; if(data.pendientes > 0) { html += '<div class="alert alert-warning fw-bold text-center mb-4 py-3 rounded-4 shadow-sm border-warning border-opacity-25"><i class="bi bi-exclamation-circle text-warning fs-5 d-block mb-1"></i> ADEUDO TOTAL: $' + data.pendientes.toFixed(2) + '</div>'; } else { html += '<div class="alert alert-success fw-bold text-center mb-4 py-3 rounded-4 shadow-sm border-success border-opacity-25"><i class="bi bi-check-circle-fill fs-5 d-block mb-1"></i> AL CORRIENTE (Sin deudas)</div>'; } html += '<div class="text-start fw-bold text-secondary mb-3 ps-2" style="font-size: 0.8rem;"><i class="bi bi-bag-check"></i> HISTORIAL DE COMPRAS:</div><div class="bg-light rounded-4 p-2 border border-light" style="max-height: 40vh; overflow-y:auto;">'; if(data.ventas.length === 0) { html += '<div class="text-muted small text-center my-3">No hay compras.</div>'; } else { data.ventas.forEach(v => { let badge = v.estado === 'PENDIENTE' ? '<span class="badge bg-secondary rounded-pill shadow-sm">DEUDA ANTIGUA</span>' : (v.estado === 'CREDITO' ? '<span class="badge bg-warning text-dark rounded-pill shadow-sm">DEBE $' + v.saldo_pendiente.toFixed(2) + '</span>' : (v.estado === 'APARTADO' ? '<span class="badge bg-info text-dark rounded-pill shadow-sm">APARTADO ($' + v.saldo_pendiente.toFixed(2) + ')</span>' : '<span class="badge bg-success rounded-pill shadow-sm">PAGADO</span>')); html += '<div class="border-bottom border-white py-3 px-2 text-start small"><div class="d-flex justify-content-between"><b class="text-dark">Ticket #' + v.id + '</b> <span>' + badge + '</span></div><div class="text-muted mt-1" style="font-size: 0.7rem;"><i class="bi bi-calendar3"></i> ' + v.fecha + '</div><div class="fw-bold text-primary mt-2 fs-6">Total: $' + v.total.toFixed(2) + '</div></div>'; }); } html += '</div>'; document.getElementById('detalle-titulo').style.display = 'none'; document.getElementById('cont-detalle').innerHTML = html; let btnEliminar = `<button class="btn btn-outline-danger w-100 mt-3 fw-bold rounded-pill border border-danger border-opacity-25" onclick="eliminarClienteDefinitivo('${nombre}')"><i class="bi bi-trash-fill"></i> ELIMINAR CLIENTE</button>`; document.getElementById('area-liquidar').innerHTML = btnEliminar; document.getElementById('modalDetalle').style.display = 'flex'; }
            
            async function eliminarClienteDefinitivo(nombre) { if(!confirm(`⚠️ ¿Estás completamente seguro de ELIMINAR a ${nombre}? Perderás su registro de puntos.`)) return; const res = await fetch('/borrar-cliente/' + encodeURIComponent(nombre), {method: 'POST'}); const data = await res.json(); if(data.ok) { alert("🗑️ Cliente eliminado correctamente."); cerrarDetalle(); cargarDirectorioCRM(); } else { alert(data.msg); } }
            
            async function subirCSV() { const input = document.getElementById('archivo-csv'); if(!input.files.length) { alert("Selecciona tu archivo .csv"); return; } const formData = new FormData(); formData.append("file", input.files[0]); try { const res = await fetch('/importar-inventario', { method: 'POST', body: formData }); const data = await res.json(); if(data.ok) { alert(data.msg); input.value = ''; ejecutarBusquedaAjustes(document.getElementById('bus-ajustes').value); } else { alert("Error: " + data.msg); } } catch(e) { alert("Error procesando el archivo."); } }

            function mostrarTicketInteractivo(titulo, totalText, msjWhatsApp) { qrcodeGen.clear(); qrcodeGen.makeCode("https://wa.me/?text=" + encodeURIComponent(msjWhatsApp)); document.getElementById('btn-wa-directo').href = "https://wa.me/?text=" + encodeURIComponent(msjWhatsApp); document.getElementById('btn-wa-directo').style.display = 'block'; document.getElementById('ticket-titulo').innerText = titulo; document.getElementById('ticket-total').innerText = totalText; document.getElementById('modalTicket').style.display = 'flex'; }
            function abrirModalCobro() { document.getElementById('modalCobro').style.display = 'flex'; document.getElementById('metodo-pago').value = 'EFECTIVO'; document.getElementById('link-archivo').value = ''; document.getElementById('descuento-manual').value = '0'; window.puntosAplicadosReal = 0; let chkPt = document.getElementById('chk-usar-puntos'); if(chkPt) chkPt.checked = false; actualizarInputsCobro(); setTimeout(() => document.getElementById('pago-cliente').focus(), 100); }
            function cerrarModalCobro() { document.getElementById('modalCobro').style.display = 'none'; }
            
            function actualizarInputsCobro() { 
                let chk = document.getElementById('chk-anticipo'); const esA = chk ? chk.checked : false; 
                let selectTipo = document.getElementById('tipo-deuda'); if(selectTipo) { selectTipo.style.display = esA ? 'block' : 'none'; }
                let chkPuntos = document.getElementById('chk-usar-puntos'); const usarPts = chkPuntos ? chkPuntos.checked : false;
                
                const metodo = document.getElementById('metodo-pago').value; const inputPago = document.getElementById('pago-cliente'); 
                document.getElementById('lbl-pago').innerText = esA ? 'ANTICIPO:' : (metodo === 'TRANSFERENCIA' ? 'TRANSFERIDO:' : 'EFECTIVO:'); document.getElementById('lbl-cambio').innerText = esA ? 'SALDO DEBE:' : 'CAMBIO:'; 
                
                let descManual = parseFloat(document.getElementById('descuento-manual').value) || 0;
                let ptsAEscontar = usarPts ? window.puntosClienteActual : 0;
                window.puntosAplicadosReal = ptsAEscontar > totalActual ? totalActual : ptsAEscontar;
                
                let totalDescuento = totalActual - window.puntosAplicadosReal - descManual;
                if(totalDescuento < 0) totalDescuento = 0;
                
                document.getElementById('total-v').innerText = '$' + totalDescuento.toFixed(2);
                
                if (!esA && metodo === 'TRANSFERENCIA') { inputPago.value = totalDescuento.toFixed(2); inputPago.disabled = true; } else { inputPago.disabled = false; } 
                calcularCambio(); 
            }
            
            function calcularCambio() { 
                const p = parseFloat(document.getElementById('pago-cliente').value) || 0; 
                let chk = document.getElementById('chk-anticipo'); const esA = chk ? chk.checked : false; 
                let descManual = parseFloat(document.getElementById('descuento-manual').value) || 0;
                let totalDescuento = totalActual - window.puntosAplicadosReal - descManual;
                if(totalDescuento < 0) totalDescuento = 0;
                
                if(esA) { const r = totalDescuento - p; document.getElementById('cambio-cliente').innerText = '$' + (r > 0 ? r.toFixed(2) : '0.00'); document.getElementById('cambio-cliente').className = 'text-warning fw-bold m-0'; } 
                else { const c = p - totalDescuento; document.getElementById('cambio-cliente').innerText = '$' + (c > 0 ? c.toFixed(2) : '0.00'); document.getElementById('cambio-cliente').className = 'text-danger fw-bold m-0'; } 
            }

            async function confirmarCobro(){ 
                const pagoStr = document.getElementById('pago-cliente').value.trim(); if (pagoStr === '') { alert("⚠️ Ingresa el monto recibido."); document.getElementById('pago-cliente').focus(); return; } const p = parseFloat(pagoStr) || 0; 
                let chk = document.getElementById('chk-anticipo'); const esA = chk ? chk.checked : false; let chkTaller = document.getElementById('chk-taller'); const enTaller = chkTaller ? chkTaller.checked : false; 
                let tipoDeuda = document.getElementById('tipo-deuda') ? document.getElementById('tipo-deuda').value : 'CREDITO';
                
                let descManual = parseFloat(document.getElementById('descuento-manual').value) || 0;
                let totalDescuento = totalActual - window.puntosAplicadosReal - descManual;
                if(totalDescuento < 0) totalDescuento = 0;

                if (!esA && p < totalDescuento) { alert("⚠️ El pago es menor al total. Activa la casilla de Deuda."); document.getElementById('pago-cliente').focus(); return; } 
                const cli = document.getElementById('nombre-cliente').value || 'Cliente de Mostrador'; const metodo = document.getElementById('metodo-pago').value; const link = document.getElementById('link-archivo').value;
                if((esA || enTaller) && document.getElementById('nombre-cliente').value.trim() === '') { alert("⚠️ Se requiere nombre para deudas o taller."); return; } 
                
                const res = await fetch('/vender', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ items: carrito, pago: p, es_anticipo: esA, tipo_deuda: tipoDeuda, cliente: cli, total: totalDescuento, metodo: metodo, en_taller: enTaller, puntos_usados: window.puntosAplicadosReal, link_archivo: link }) }); 
                if(res.ok) { 
                    const d = await res.json(); 
                    let msjSub = "PAGADO: $" + totalDescuento.toFixed(2);
                    if(esA) { msjSub = tipoDeuda === 'APARTADO' ? "APARTADO - RESTA: $" + (totalDescuento-p).toFixed(2) : "CRÉDITO - RESTA: $" + (totalDescuento-p).toFixed(2); }
                    cerrarModalCobro(); mostrarTicketInteractivo("COBRO EXITOSO", msjSub, d.mensaje_whatsapp); 
                    if(cli !== 'Cliente de Mostrador') cargarDirectorioCRM(); 
                } 
            }
            
            async function guardarCotizacion() { 
                const cli = document.getElementById('nombre-cliente').value; const link = document.getElementById('link-archivo').value;
                let descManual = parseFloat(document.getElementById('descuento-manual').value) || 0;
                let totalDescuento = totalActual - window.puntosAplicadosReal - descManual;
                if(totalDescuento < 0) totalDescuento = 0;

                if(!cli) { alert("⚠️ Para cotizar, escribe el nombre del cliente primero."); document.getElementById('nombre-cliente').focus(); return; } if(carrito.length === 0) return; 
                const res = await fetch('/guardar-cotizacion', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ items: carrito, cliente: cli, total: totalDescuento, link_archivo: link }) }); 
                if(res.ok) { 
                    const d = await res.json(); 
                    cerrarModalCobro(); 
                    
                    // GUARDAMOS EN MEMORIA PARA LA IMPRESORA ANTES DE BORRAR EL CARRITO
                    window.ultimaVentaDatos = {
                        razon: (document.getElementById('cfg-razon') && document.getElementById('cfg-razon').value) ? document.getElementById('cfg-razon').value : nombreComercial,
                        rfc: (document.getElementById('cfg-rfc') && document.getElementById('cfg-rfc').value) ? document.getElementById('cfg-rfc').value : "RFC: GENERICO",
                        dir: (document.getElementById('cfg-dir') && document.getElementById('cfg-dir').value) ? document.getElementById('cfg-dir').value : "Dirección no configurada",
                        tel: (document.getElementById('cfg-tel') && document.getElementById('cfg-tel').value) ? document.getElementById('cfg-tel').value : "Tel: ---",
                        msj: "¡Cotización válida por 15 días!",
                        items: [...carrito], // Copia exacta de lo cotizado
                        total: totalDescuento,
                        pago: 0,
                        folio: "COTIZACIÓN"
                    };

                    mostrarTicketInteractivo("COTIZACIÓN GUARDADA", "Total Estimado: $" + totalDescuento.toFixed(2), d.mensaje_whatsapp); 
                    cancelarVenta(); 
                } 
            }
            
            async function cargarCotizaciones() { const res = await fetch('/lista-cotizaciones'); const datos = await res.json(); const lista = document.getElementById('lista-cotizaciones'); lista.innerHTML = ''; if (datos.length === 0) { lista.innerHTML = '<div class="text-center text-muted mt-3">No hay cotizaciones activas.</div>'; return; } datos.forEach(c => { lista.innerHTML += `<div class="card-pro d-flex justify-content-between align-items-center mb-2 px-4 shadow-sm"><div><div class="fw-bold text-dark">#${c.id} - ${c.cliente}</div><div class="text-primary fw-bold">$${parseFloat(c.total).toFixed(2)}</div><small class="text-muted"><i class="bi bi-calendar2"></i> ${c.fecha}</small></div><div class="d-flex gap-2"><button class="btn btn-light text-danger border rounded-circle shadow-sm" style="width:40px;height:40px;" onclick="borrarCotizacion(${c.id})"><i class="bi bi-trash"></i></button><button class="btn btn-primary rounded-pill fw-bold shadow-sm px-3" onclick="verDetalleCotizacion(${c.id}, \\'${c.link_archivo || ''}\\')"><i class="bi bi-eye me-1"></i> Ver</button></div></div>`; }); }
            async function borrarCotizacion(id) { if (!confirm('¿Deseas eliminar esta cotización permanentemente?')) return; const res = await fetch(`/borrar-cotizacion/${id}`, { method: 'POST' }); if (res.ok) { cargarCotizaciones(); } }
            
            async function verDetalleCotizacion(id, linkArchivo) { 
                const res = await fetch(`/detalle-cotizacion/${id}`); const items = await res.json(); const resList = await fetch('/lista-cotizaciones'); const todas = await resList.json(); const info = todas.find(c => c.id === id); 
                document.getElementById('detalle-titulo').innerText = "COTIZACIÓN #" + id; document.getElementById('detalle-titulo').style.display = 'block'; 
                let html = '<div class="list-group list-group-flush mb-3 bg-transparent">'; items.forEach(i => { html += `<div class="list-group-item d-flex justify-content-between bg-transparent border-light px-1"><span class="text-dark">${i.desc} <span class="badge bg-secondary ms-1 rounded-pill">x${i.cant}</span></span><b class="text-primary">$${(i.pre * i.cant).toFixed(2)}</b></div>`; }); html += '</div>'; 
                
                if(linkArchivo && linkArchivo !== 'null' && linkArchivo !== '') { html += `<div class="mb-3 text-center"><a href="${linkArchivo}" target="_blank" class="btn btn-sm btn-outline-primary rounded-pill fw-bold"><i class="bi bi-cloud-arrow-down-fill me-1"></i> Ver Archivos / Drive</a></div>`; }
                
                document.getElementById('cont-detalle').innerHTML = html; 

                // MEMORIA PARA IMPRIMIR LA COTIZACIÓN HISTÓRICA
                window.ultimaVentaDatos = {
                    razon: (document.getElementById('cfg-razon') && document.getElementById('cfg-razon').value) ? document.getElementById('cfg-razon').value : nombreComercial,
                    rfc: (document.getElementById('cfg-rfc') && document.getElementById('cfg-rfc').value) ? document.getElementById('cfg-rfc').value : "RFC: GENERICO",
                    dir: (document.getElementById('cfg-dir') && document.getElementById('cfg-dir').value) ? document.getElementById('cfg-dir').value : "Dirección no configurada",
                    tel: (document.getElementById('cfg-tel') && document.getElementById('cfg-tel').value) ? document.getElementById('cfg-tel').value : "Tel: ---",
                    msj: "¡Cotización válida por 15 días!",
                    items: items,
                    total: parseFloat(info.total),
                    pago: 0,
                    folio: "COT-" + id
                };

                let btnImprimir = `<button class="btn btn-light w-100 fw-bold shadow-sm mb-3 text-primary border rounded-pill py-3" onclick="imprimirTicketFisico()"><i class="bi bi-printer-fill me-1"></i> IMPRIMIR COTIZACIÓN</button>`;
                let btnRetomar = `<button class="btn btn-success btn-lg w-100 fw-bold shadow-sm rounded-pill" onclick='retomarCotizacion(${JSON.stringify(items)}, "${info.cliente}")'><i class="bi bi-cart-check me-2"></i> COBRAR AHORA</button>`; 
                
                document.getElementById('area-liquidar').innerHTML = btnImprimir + btnRetomar; 
                document.getElementById('modalDetalle').style.display = 'flex'; 
            }
            function retomarCotizacion(items, cliente) { carrito = items.map(i => ({ cod: i.cod, desc: i.desc, pre: i.pre, cant: i.cant, stock: '-', unidad: 'PZ', p2:0, cp2:0, p3:0, cp3:0, pe:0 })); document.getElementById('nombre-cliente').value = cliente; cerrarDetalle(); switchTab('venta'); actualizarVistaCarrito(); }

            function agregarAlCarrito(cod, desc, pre, stock, unidad = 'PZ', p2 = 0, cp2 = 0, p3 = 0, cp3 = 0, pe = 0){ const ex = carrito.find(i => i.cod === cod); if(ex) { ex.cant++; } else { carrito.unshift({cod, desc, pre, stock, cant: 1, unidad, p2, cp2, p3, cp3, pe}); } indiceCarritoSel = -1; if(document.getElementById('bus-v')) { document.getElementById('bus-v').value = ''; document.getElementById('res-v').innerHTML = ''; document.getElementById('bus-v').focus(); } actualizarVistaCarrito(); }

            // Variables para controlar en qué estado estamos
let alertaCancelacionActiva = false;
let navegandoCarrito = false;
let filaActual = 0;

document.addEventListener('keydown', function(event) {
    // 1. LÓGICA PARA LA TECLA ESCAPE (Cancelar Venta)
    if (event.key === "Escape") {
        if (carrito.length > 0 && !alertaCancelacionActiva) {
            alertaCancelacionActiva = true;
            document.getElementById('modal-alerta-esc').style.display = 'block';
            return;
        }
        if (alertaCancelacionActiva) {
            carrito = [];
            actualizarVistaCarrito();
            cerrarAlerta();
            return;
        }
    }

    // 2. LÓGICA PARA LA TECLA ENTER (Si la alerta está activa)
    if (event.key === "Enter" && alertaCancelacionActiva) {
        cerrarAlerta();
        return;
    }

    // 3. ENTRAR AL CARRITO (F3)
    if (event.key === "F3") {
        event.preventDefault(); 
        if (carrito.length > 0) {
            navegandoCarrito = true;
            filaActual = 0; 
            resaltarFila();
            // Le quitamos el foco al buscador para que no escriba nada accidentalmente
            if(document.getElementById('bus-v')) document.getElementById('bus-v').blur();
        }
        return;
    }

    // 4. SALIR DEL CARRITO (F2) Y VOLVER AL BUSCADOR
    if (event.key === "F2" && navegandoCarrito) {
        event.preventDefault();
        navegandoCarrito = false;
        quitarResaltado();
        if(document.getElementById('bus-v')) document.getElementById('bus-v').focus();
        return;
    }

    // 5. NAVEGAR Y SUMAR/RESTAR EN EL CARRITO (Solo si presionó F3 antes)
    if (navegandoCarrito && !alertaCancelacionActiva) {
        
        // Bloqueamos las teclas de navegación y signos para que no hagan cosas raras en el navegador
        if (["ArrowDown", "ArrowUp", "+", "-", "Add", "Subtract"].includes(event.key)) {
            event.preventDefault();
        }

        if (event.key === "ArrowDown") {
            filaActual = Math.min(filaActual + 1, carrito.length - 1);
            resaltarFila();
        } 
        else if (event.key === "ArrowUp") {
            filaActual = Math.max(filaActual - 1, 0);
            resaltarFila();
        } 
        else if (event.key === "+" || event.key === "Add") {
            modificarCant(filaActual, 1);
            // Damos 50 milisegundos para que la tabla se redibuje antes de volver a pintarla
            setTimeout(() => { 
                resaltarFila(); 
                if(document.getElementById('bus-v')) document.getElementById('bus-v').blur();
            }, 50);
        } 
        else if (event.key === "-" || event.key === "Subtract") {
            modificarCant(filaActual, -1);
            setTimeout(() => {
                if (filaActual >= carrito.length) filaActual = Math.max(carrito.length - 1, 0);
                
                if (carrito.length > 0) {
                    resaltarFila();
                    if(document.getElementById('bus-v')) document.getElementById('bus-v').blur();
                } else {
                    // Si restó el último producto a cero y el carrito se vació, salimos automáticamente
                    navegandoCarrito = false;
                    if(document.getElementById('bus-v')) document.getElementById('bus-v').focus();
                }
            }, 50);
        }
    }
});

// === FUNCIONES AUXILIARES ===
function cerrarAlerta() {
    alertaCancelacionActiva = false;
    document.getElementById('modal-alerta-esc').style.display = 'none';
    if(document.getElementById('bus-v')) document.getElementById('bus-v').focus();
}

function resaltarFila() {
    quitarResaltado();
    let filas = document.querySelectorAll('#tabla-carrito tbody tr');
    if(filas[filaActual]) {
        filas[filaActual].style.backgroundColor = '#4b5563'; 
        filas[filaActual].style.color = '#fff';
        
        // Si hay botones adentro (como los de basura), asegurarnos de que se vean bien
        let botones = filas[filaActual].querySelectorAll('button');
        botones.forEach(b => b.style.opacity = '1');
    }
}


function quitarResaltado() {
    let filas = document.querySelectorAll('#tabla-carrito tbody tr');
    filas.forEach(f => {
        f.style.backgroundColor = '';
        f.style.color = '';
    });
}

            function modificarCant(index, delta) { if(carrito[index].cant + delta > 0) { carrito[index].cant += delta; actualizarVistaCarrito(); } else { eliminarDelCarrito(index); } }
            function cambiarCantManual(index, nuevoValor) { let esPieza = carrito[index].unidad === 'PZ'; let val = esPieza ? parseInt(nuevoValor) : parseFloat(nuevoValor); if (isNaN(val) || val <= 0) { val = 1; } carrito[index].cant = val; actualizarVistaCarrito(); }
            async function pesarArticulo(index) { let btn = document.querySelectorAll('.btn-warning[title="Leer Báscula"]')[index]; let contenidoOriginal = btn.innerHTML; btn.innerHTML = '<i class="bi bi-arrow-repeat spin"></i>'; btn.disabled = true; try { const res = await fetch('/leer-bascula'); const data = await res.json(); if(data.ok) { carrito[index].cant = data.peso; actualizarVistaCarrito(); } else { alert(data.msg); } } catch (e) { alert("Error al conectar con la báscula USB."); } finally { if(document.querySelectorAll('.btn-warning[title="Leer Báscula"]')[index]){ let btnRecuperado = document.querySelectorAll('.btn-warning[title="Leer Báscula"]')[index]; btnRecuperado.innerHTML = contenidoOriginal; btnRecuperado.disabled = false; } } }
            
            function actualizarVistaCarrito(){
                const div = document.getElementById('items-carrito'); const footer = document.getElementById('footer-mini');
                if(carrito.length === 0) { document.getElementById('carrito-seccion').style.display = 'none'; footer.style.display = 'none'; return; }
                document.getElementById('carrito-seccion').style.display = 'block'; footer.style.display = 'block'; div.innerHTML = ''; totalActual = 0; let hoy = new Date().toISOString().split('T')[0];
                let esVip = document.getElementById('chk-vip') ? document.getElementById('chk-vip').checked : false;

                carrito.forEach((i, idx) => {
                    let precioBase = parseFloat(i.pre); let subtotal = 0; let txtPromo = ''; let precioUnidadMostrado = `$${precioBase.toFixed(2)} c/u`; 
                    let promo = promocionesCache.find(p => p.codigo_producto === i.cod && p.fecha_inicio <= hoy && p.fecha_fin >= hoy);
                    
                    if(promo) { 
                        if (promo.cantidad_requerida === 1) { subtotal = i.cant * promo.precio_promocional; precioUnidadMostrado = `<s>$${precioBase.toFixed(2)}</s> <b class="text-danger">$${promo.precio_promocional.toFixed(2)}</b>`; txtPromo = `<div class="badge bg-danger text-white mt-1 rounded-pill"><i class="bi bi-tag-fill"></i> ¡Oferta!</div>`; } 
                        else { let cantCombos = Math.floor(i.cant / promo.cantidad_requerida); let cantSueltos = i.cant % promo.cantidad_requerida; if (cantCombos > 0) { subtotal = (cantCombos * promo.precio_promocional) + (cantSueltos * precioBase); txtPromo = `<div class="badge bg-warning text-dark mt-1 rounded-pill"><i class="bi bi-star-fill"></i> Combo aplicado</div>`; } else { subtotal = i.cant * precioBase; txtPromo = `<div class="badge bg-info text-dark mt-1 rounded-pill"><i class="bi bi-info-circle"></i> Lleva ${promo.cantidad_requerida} x $${promo.precio_promocional.toFixed(2)}</div>`; } } 
                    } else { 
                        let precioAplicar = precioBase;
                        if (esVip && parseFloat(i.pe) > 0) {
                            precioAplicar = parseFloat(i.pe);
                            txtPromo = `<div class="badge bg-warning text-dark mt-1 rounded-pill"><i class="bi bi-star-fill"></i> Precio VIP</div>`;
                        } else if (parseFloat(i.cp3) > 0 && i.cant >= parseFloat(i.cp3) && parseFloat(i.p3) > 0) {
                            precioAplicar = parseFloat(i.p3);
                            txtPromo = `<div class="badge bg-success mt-1 rounded-pill"><i class="bi bi-box-seam"></i> Mayoreo 3</div>`;
                        } else if (parseFloat(i.cp2) > 0 && i.cant >= parseFloat(i.cp2) && parseFloat(i.p2) > 0) {
                            precioAplicar = parseFloat(i.p2);
                            txtPromo = `<div class="badge bg-info text-dark mt-1 rounded-pill"><i class="bi bi-tags"></i> Mayoreo 2</div>`;
                        }
                        subtotal = i.cant * precioAplicar; 
                        if(precioAplicar !== precioBase) { precioUnidadMostrado = `<s>$${precioBase.toFixed(2)}</s> <b class="text-primary">$${precioAplicar.toFixed(2)}</b>`; } 
                        else { precioUnidadMostrado = `$${precioBase.toFixed(2)} c/u`; }
                    }
                    totalActual += subtotal; let stepInput = i.unidad === 'PZ' ? '1' : '0.001'; let btnBascula = i.unidad === 'KG' ? `<button type="button" class="btn btn-warning btn-sm px-3 rounded-end-pill border-start border-warning" onclick="pesarArticulo(${idx})" title="Leer Báscula"><i class="bi bi-speedometer"></i></button>` : ''; let extraBordeDerecho = i.unidad === 'KG' ? '0' : '50rem'; 
                    let estadoVisual = (idx === indiceCarritoSel) ? 'box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.4); border-color: #ef4444 !important; background: #fff5f5;' : '';
                    div.innerHTML += `<div class="cart-item-card d-flex justify-content-between align-items-center" style="${estadoVisual}"><div style="line-height: 1.2; flex-grow: 1; padding-right: 10px;"><div class="fw-bold text-dark fs-6" style="letter-spacing: -0.3px;">${i.desc}</div><small class="text-muted" style="font-size:0.75rem;">${precioUnidadMostrado}</small><br>${txtPromo}</div><div class="d-flex align-items-center gap-3"><div class="btn-group shadow-sm bg-white" role="group" style="border-radius: 50rem;"><button type="button" class="btn btn-light btn-sm px-3 border text-secondary" style="border-radius: 50rem 0 0 50rem;" onclick="modificarCant(${idx}, -1)"><b><i class="bi bi-dash"></i></b></button><input type="number" class="form-control form-control-sm text-center fw-bold border-top border-bottom border-0 bg-transparent text-dark" style="width: 50px; -moz-appearance: textfield;" step="${stepInput}" value="${i.cant}" onchange="cambiarCantManual(${idx}, this.value)"><button type="button" class="btn btn-light btn-sm px-3 border text-secondary" style="border-radius: 0 ${extraBordeDerecho} ${extraBordeDerecho} 0;" onclick="modificarCant(${idx}, 1)"><b><i class="bi bi-plus"></i></b></button>${btnBascula}</div><div class="fw-bold text-primary text-end fs-5" style="min-width:75px; letter-spacing: -0.5px;">$${subtotal.toFixed(2)}</div><button class="btn btn-light text-danger rounded-circle shadow-sm border ms-2 d-flex justify-content-center align-items-center" style="width:35px; height:35px;" onclick="eliminarDelCarrito(${idx})"><i class="bi bi-x-lg"></i></button></div></div>`;
                });
                document.getElementById('total-mini').innerText = '$' + totalActual.toFixed(2); document.getElementById('total-v').innerText = '$' + totalActual.toFixed(2); calcularCambio();
            }

            function eliminarDelCarrito(index){ carrito.splice(index, 1); if (indiceCarritoSel >= carrito.length) indiceCarritoSel = carrito.length - 1; if (carrito.length === 0) { indiceCarritoSel = -1; let b = document.getElementById('bus-v'); if(b) b.focus(); } actualizarVistaCarrito(); }
            function cancelarVenta() { carrito=[]; actualizarVistaCarrito(); document.getElementById('nombre-cliente').value = ''; document.getElementById('pago-cliente').value = ''; let chkT = document.getElementById('chk-taller'); if(chkT) chkT.checked = false;}

            async function cargarTaller() { const res = await fetch('/pedidos-taller'); const pedidos = await res.json(); document.getElementById('kb-fila').innerHTML = ''; document.getElementById('kb-produccion').innerHTML = ''; document.getElementById('kb-listo').innerHTML = ''; if(pedidos.length === 0) { document.getElementById('kb-fila').innerHTML = '<div class="text-center text-muted mt-4 small"><i class="bi bi-inbox fs-2 opacity-50 d-block mb-2"></i> No hay trabajos.</div>'; return; } pedidos.forEach(p => { let card = '<div class="kanban-card"><div class="fw-bold text-dark small mb-2 d-flex justify-content-between"><span>#' + p.id + '</span><span class="text-primary">' + p.cliente + '</span></div><div class="text-muted bg-light p-2 rounded-3 mb-3" style="font-size: 0.75rem; line-height:1.4;">'; p.items.forEach(item => { card += '• <b class="text-dark">' + item.cantidad + 'x</b> ' + item.descripcion + '<br>'; }); card += '</div>'; if(p.estado_produccion === 'FILA') { card += `<button class="btn btn-warning btn-sm w-100 fw-bold text-dark rounded-pill shadow-sm" style="font-size:0.75rem;" onclick="cambiarEstadoTaller(${p.id}, 'PRODUCCION', '${p.telefono || ''}', '${p.cliente}')">A Producción <i class="bi bi-arrow-right"></i></button>`; document.getElementById('kb-fila').innerHTML += card + '</div>'; } else if(p.estado_produccion === 'PRODUCCION') { card += `<button class="btn btn-success btn-sm w-100 fw-bold rounded-pill shadow-sm" style="font-size:0.75rem;" onclick="cambiarEstadoTaller(${p.id}, 'LISTO', '${p.telefono || ''}', '${p.cliente}')"><i class="bi bi-check2-all me-1"></i> Marcar Terminado</button>`; document.getElementById('kb-produccion').innerHTML += card + '</div>'; } else if(p.estado_produccion === 'LISTO') { card += `<button class="btn btn-dark btn-sm w-100 fw-bold rounded-pill shadow-sm" style="font-size:0.75rem;" onclick="cambiarEstadoTaller(${p.id}, 'ENTREGADO', '${p.telefono || ''}', '${p.cliente}')"><i class="bi bi-box-arrow-right me-1"></i> Entregar a Cliente</button>`; document.getElementById('kb-listo').innerHTML += card + '</div>'; } }); }
            async function cambiarEstadoTaller(id, nuevo_estado, tel, cliente) { 
                await fetch('/actualizar-taller', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({id: id, estado: nuevo_estado}) }); 
                if (nuevo_estado === 'LISTO' && tel && tel !== 'undefined' && tel !== 'null' && tel !== '') {
                    let msj = `¡Hola ${cliente}! 👋 Te avisamos que tu pedido en *${nombreComercial}* (Ticket #${id}) ya está LISTO para entrega. ¡Te esperamos!`;
                    window.open("https://wa.me/" + tel + "?text=" + encodeURIComponent(msj), '_blank');
                }
                cargarTaller(); 
            }
            
            function cerrarDetalle() { document.getElementById('modalDetalle').style.display = 'none'; }
            function abrirTemporal() { document.getElementById('modalTemporal').style.display = 'flex'; document.getElementById('temp-desc').focus(); }
            function cerrarTemporal() { document.getElementById('modalTemporal').style.display = 'none'; }
            function agregarTemporal() { const d = document.getElementById('temp-desc').value; const p = parseFloat(document.getElementById('temp-pre').value); if(!d || isNaN(p)) return; carrito.push({ cod: 'TEMP-' + Date.now(), desc: d, pre: p, stock: '-', cant: 1, unidad: 'PZ', p2:0, cp2:0, p3:0, cp3:0, pe:0 }); cerrarTemporal(); actualizarVistaCarrito(); document.getElementById('temp-desc').value = ''; document.getElementById('temp-pre').value = ''; }

            async function cargarMiTurno(){ 
                const res = await fetch('/mi-turno'); const d = await res.json(); 
                document.getElementById('turno-fon').innerText = '$' + d.fondo.toFixed(2); 
                document.getElementById('turno-efe').innerText = '$' + d.efectivo.toFixed(2); 
                document.getElementById('turno-tar').innerText = '$' + d.tarjeta.toFixed(2); 
                document.getElementById('turno-gas').innerText = '-$' + d.gastos.toFixed(2); 
                document.getElementById('turno-cajon').innerText = '$' + d.cajon.toFixed(2); 
            }

            async function registrarFondo() { 
                let val = prompt('¿Con cuánto dinero (morralla) inicias la caja para dar cambios?', ''); 
                if (val === null || val.trim() === '') return; 
                let monto = parseFloat(val); if (isNaN(monto) || monto <= 0) return; 
                const res = await fetch('/fondo-caja', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({monto: monto}) }); 
                if(res.ok) { cargarMiTurno(); } 
            }

            function cerrarTurno() { const caja = document.getElementById('turno-cajon').innerText; const msj = `*CORTE DE TURNO Z*\\nCajero: ${nombreCajero}\\n\\n💵 Total a entregar en caja: *${caja}*\\n\\n(Turno cerrado correctamente)`; mostrarTicketInteractivo("CORTE DE TURNO", "Entregar: " + caja, msj); }
            function registrarGasto() { document.getElementById('modalRetiro').style.display = 'flex'; setTimeout(() => document.getElementById('desc-gasto').focus(), 100); }
            async function confirmarGasto() { const desc = document.getElementById('desc-gasto').value; const monto = parseFloat(document.getElementById('monto-gasto').value); if(!desc || isNaN(monto) || monto <= 0) { alert("Datos inválidos."); return; } const res = await fetch('/gasto', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({desc, monto}) }); if(res.ok) { document.getElementById('desc-gasto').value = ''; document.getElementById('monto-gasto').value = ''; document.getElementById('modalRetiro').style.display = 'none'; alert("Retiro guardado."); cargarReportes(); cargarMiTurno(); } }
            
            async function cargarReportes(){ 
                const inicio = document.getElementById('rep-inicio').value; const fin = document.getElementById('rep-fin').value; const cajeroSelec = document.getElementById('rep-cajero') ? document.getElementById('rep-cajero').value : 'TODOS'; 
                const res = await fetch('/generar-reporte', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({inicio: inicio, fin: fin, cajero: cajeroSelec}) }); 
                const d = await res.json(); 
                document.getElementById('rep-total-ventas').innerText = '$' + d.total_ventas.toFixed(2); document.getElementById('rep-efectivo').innerText = '$' + d.suma_efectivo.toFixed(2); document.getElementById('rep-transferencia').innerText = '$' + d.suma_transferencia.toFixed(2); document.getElementById('rep-utilidad').innerText = '$' + d.total_utilidad.toFixed(2); document.getElementById('rep-conteo').innerText = d.total_items + ' items vendidos'; 
                const tbody = document.getElementById('tabla-reporte-cuerpo'); tbody.innerHTML = ''; 
                
                if (d.detalle.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="5" class="text-center py-3 text-muted">No hay movimientos en este periodo.</td></tr>';
                    return;
                }

                d.detalle.forEach(item => { 
                    if (item.tipo === 'retiro') {
                        tbody.innerHTML += '<tr class="border-bottom border-danger border-opacity-25" style="background-color: #fff5f5;"><td class="ps-3 py-1 text-danger small"><i class="bi bi-arrow-down-right-circle-fill me-1"></i>' + item.fecha + '</td><td class="fw-bold text-danger py-1">RETIRO: ' + item.desc + '</td><td class="text-center py-1 text-danger fw-bold">-</td><td class="fw-bold text-danger py-1">-$' + item.total.toFixed(2) + '</td><td class="small text-danger opacity-75 pe-3 py-1">' + item.cajero + '</td></tr>';
                    } else {
                        let ico = item.metodo === 'TRANSFERENCIA' ? '<i class="bi bi-credit-card-fill text-info ms-2" title="Tarjeta"></i>' : '';
                        tbody.innerHTML += '<tr class="border-bottom border-light"><td class="ps-3 py-1 text-muted small">' + item.fecha + '</td><td class="fw-bold text-dark py-1">' + item.desc + ico + '</td><td class="text-center py-1"><span class="badge bg-light text-dark border rounded-pill">' + item.cant + '</span></td><td class="fw-bold text-primary py-1">$' + item.total.toFixed(2) + '</td><td class="small text-muted pe-3 py-1">' + item.cajero + '</td></tr>'; 
                    }
                }); 
            }
            
            async function cargarComboCajeros() { const res = await fetch('/equipo'); const datos = await res.json(); const combo = document.getElementById('rep-cajero'); if(combo) { combo.innerHTML = '<option value="TODOS">Todos</option><option value="SISTEMA">Dueño / Sistema</option>'; datos.forEach(u => { combo.innerHTML += '<option value="' + u.nombre + '">' + u.nombre + '</option>'; }); } }

            async function cargarPendientes() { const res = await fetch('/pendientes'); const datos = await res.json(); const lista = document.getElementById('lista-pendientes'); lista.innerHTML = ''; datos.forEach(v => { let bg = v.estado === 'APARTADO' ? 'bg-info bg-opacity-10 border-info' : 'bg-warning bg-opacity-10 border-warning'; let textC = v.estado === 'APARTADO' ? 'text-info' : 'text-warning'; let icon = v.estado === 'APARTADO' ? 'bi-box-seam' : 'bi-cash-coin'; lista.innerHTML += '<div class="card-pro d-flex justify-content-between align-items-center px-4 shadow-sm" onclick="verDetalleNota(' + v.id + ', \\'' + v.estado + '\\', ' + v.saldo_pendiente + ', \\'' + v.cliente + '\\', ' + v.total + ', \\'' + (v.link_archivo || '') + '\\')" style="cursor:pointer; border-left: 4px solid var(--bs-' + (v.estado==='APARTADO'?'info':'warning') + ');"><div><div class="fw-bold text-dark fs-5">' + v.cliente + '</div><div class="text-danger fw-bold fs-6">Debe: $' + parseFloat(v.saldo_pendiente).toFixed(2) + '</div><small class="text-muted">Folio #' + v.id + ' | ' + v.fecha + '</small></div><div class="' + bg + ' rounded-circle d-flex align-items-center justify-content-center" style="width:45px; height:45px;"><i class="bi ' + icon + ' ' + textC + ' fs-3"></i></div></div>'; }); }
            async function cargarHistorial() { const res = await fetch('/historial'); const ventas = await res.json(); const lista = document.getElementById('lista-historial'); lista.innerHTML = ''; ventas.forEach(v => { let estBadge = v.estado === 'PENDIENTE' ? '<span class="badge bg-secondary rounded-pill shadow-sm"><i class="bi bi-clock me-1"></i> ANTIGUA</span>' : (v.estado === 'CREDITO' ? '<span class="badge bg-warning text-dark rounded-pill shadow-sm"><i class="bi bi-clock me-1"></i> CRÉDITO</span>' : (v.estado === 'APARTADO' ? '<span class="badge bg-info text-dark rounded-pill shadow-sm"><i class="bi bi-box me-1"></i> APARTADO</span>' : '<span class="badge bg-success rounded-pill shadow-sm"><i class="bi bi-check-lg me-1"></i> PAGADO</span>')); lista.innerHTML += '<div class="card-pro d-flex justify-content-between align-items-center px-4 py-3 shadow-sm" onclick="verDetalleNota(' + v.id + ', \\'' + v.estado + '\\', ' + v.saldo_pendiente + ', \\'' + v.cliente + '\\', ' + v.total + ', \\'' + (v.link_archivo || '') + '\\')" style="cursor:pointer;"><div><div class="fw-bold text-dark fs-6">Folio #' + v.id + ' <span class="ms-2">' + estBadge + '</span></div><div class="text-primary fw-bold fs-5 mt-1">$' + parseFloat(v.total).toFixed(2) + '</div><div class="text-secondary fw-bold mt-1 small">' + v.cliente + '</div><small class="text-muted" style="font-size:0.7rem;">' + v.fecha + '</small></div><i class="bi bi-chevron-right text-muted fs-4"></i></div>'; }); }
            
            async function verDetalleNota(id, estado, resta, cliente, total, linkArchivo) { 
                const resI = await fetch('/detalle-venta/' + id); const items = await resI.json(); const resA = await fetch('/abonos/' + id); const abonos = await resA.json(); 
                document.getElementById('detalle-titulo').innerText = "ESTADO DE CUENTA #" + id; document.getElementById('detalle-titulo').style.display = 'block'; 
                
                let html = '<div class="mb-3 fw-bold text-secondary ps-1"><i class="bi bi-box-seam text-primary"></i> MERCANCÍA:</div><div class="bg-white rounded-3 shadow-sm border border-light p-2 mb-4">'; items.forEach(i => { html += '<div class="d-flex justify-content-between border-bottom border-light py-2 px-1"><span class="text-dark">' + i.descripcion + ' <span class="badge bg-light text-dark border rounded-pill ms-1">x' + i.cantidad + '</span></span><b class="text-primary">$' + parseFloat(i.total_cobrado).toFixed(2) + '</b></div>'; }); html += '</div>'; 
                
                if(linkArchivo && linkArchivo !== 'null' && linkArchivo !== '') { html += `<div class="mb-4 text-center"><a href="${linkArchivo}" target="_blank" class="btn btn-sm btn-outline-primary rounded-pill fw-bold"><i class="bi bi-cloud-arrow-down-fill me-1"></i> Ver Archivos / Drive</a></div>`; }
                
                if(abonos.length > 0) { html += '<div class="mb-2 fw-bold text-success ps-1"><i class="bi bi-journal-arrow-down"></i> PAGOS:</div><div class="bg-white rounded-3 shadow-sm border border-light p-2">'; abonos.forEach(a => { html += '<div class="d-flex justify-content-between text-muted small border-bottom border-light py-2 px-1"><span><i class="bi bi-calendar3"></i> ' + a.fecha + '</span><span class="text-success fw-bold fs-6">+$' + parseFloat(a.monto).toFixed(2) + '</span></div>'; }); html += '</div>'; } 
                
                document.getElementById('cont-detalle').innerHTML = html; 

                // --- AQUÍ GUARDAMOS LOS DATOS PARA LA REIMPRESIÓN ---
                let totalPagado = abonos.reduce((acc, a) => acc + parseFloat(a.monto), 0);
                window.ultimaVentaDatos = {
                    razon: (document.getElementById('cfg-razon') && document.getElementById('cfg-razon').value) ? document.getElementById('cfg-razon').value : nombreComercial,
                    rfc: (document.getElementById('cfg-rfc') && document.getElementById('cfg-rfc').value) ? document.getElementById('cfg-rfc').value : "RFC: GENERICO",
                    dir: (document.getElementById('cfg-dir') && document.getElementById('cfg-dir').value) ? document.getElementById('cfg-dir').value : "Dirección no configurada",
                    tel: (document.getElementById('cfg-tel') && document.getElementById('cfg-tel').value) ? document.getElementById('cfg-tel').value : "Tel: ---",
                    msj: (document.getElementById('cfg-msg') && document.getElementById('cfg-msg').value) ? document.getElementById('cfg-msg').value : "¡Gracias por su preferencia!",
                    items: items, // Los productos de la nota vieja
                    total: parseFloat(total),
                    pago: totalPagado,
                    folio: id
                };
                
                let htmlBotones = `<button class="btn btn-light w-100 fw-bold shadow-sm mb-3 text-primary border rounded-pill py-3" onclick="imprimirTicketFisico()"><i class="bi bi-printer-fill me-1"></i> REIMPRIMIR TICKET FÍSICO</button>`; 
                if(estado === 'PENDIENTE' || estado === 'CREDITO' || estado === 'APARTADO') { htmlBotones += '<button class="btn btn-primary btn-lg w-100 fw-bold shadow rounded-pill py-3" style="background: linear-gradient(145deg, #0d6efd, #0b5ed7); border: none;" onclick="liquidarVenta(' + id + ', ' + resta + ', \\'' + cliente + '\\')"><i class="bi bi-cash-stack me-1"></i> RECIBIR PAGO</button>'; } else { htmlBotones += '<div class="alert alert-success text-center mt-3 fw-bold fs-6 rounded-pill border-success border-opacity-25 shadow-sm py-3"><i class="bi bi-check-circle-fill fs-5 me-1"></i> NOTA LIQUIDADA</div>'; } 
                document.getElementById('area-liquidar').innerHTML = htmlBotones; document.getElementById('modalDetalle').style.display = 'flex'; 
            }
            async function liquidarVenta(id, resta, cliente) { let abonoStr = prompt('Saldo del cliente ' + cliente + ': $' + resta.toFixed(2) + '\\n\\nIngresa el monto del pago:', resta); if(abonoStr === null) return; let abono = parseFloat(abonoStr); if(isNaN(abono) || abono <= 0) return; if(abono > resta) abono = resta; const res = await fetch('/liquidar', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ id: id, monto: abono, cliente: cliente }) }); if(res.ok) { document.getElementById('modalDetalle').style.display = 'none'; alert("Abono procesado."); cargarPendientes(); } }
            async function cargarUsuarios() { const res = await fetch('/equipo'); const datos = await res.json(); const lista = document.getElementById('lista-equipo'); lista.innerHTML = ''; datos.forEach(u => { let icon = u.rol === 'admin' ? '<i class="bi bi-star-fill text-warning"></i> ADMIN' : '<i class="bi bi-person-fill text-success"></i> CAJERO'; lista.innerHTML += '<div class="card-pro d-flex justify-content-between align-items-center mb-2 px-4 shadow-sm"><div><div class="fw-bold text-dark fs-5">' + u.nombre + '</div><small class="text-muted">' + icon + '</small></div><button class="btn btn-light text-danger rounded-circle shadow-sm border" style="width:40px;height:40px;" onclick="borrarUsuario(' + u.id + ', \\'' + u.nombre + '\\')"><i class="bi bi-person-x-fill"></i></button></div>'; }); }
            async function crearUsuario() { const u = document.getElementById('nu-nombre').value.trim(); const p = document.getElementById('nu-pin').value.trim(); const r = document.getElementById('nu-rol').value; if(!u || !p) return; const res = await fetch('/nuevo-miembro', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({u, p, r}) }); if(res.ok) { document.getElementById('nu-nombre').value = ''; document.getElementById('nu-pin').value = ''; cargarUsuarios(); } }
            async function borrarUsuario(id, nombre) { if(confirm('¿Despedir a ' + nombre + '?')) { await fetch('/borrar-miembro/' + id, { method: 'POST' }); cargarUsuarios(); } }

            let itemsAjusteCache = [];
            async function ejecutarBusquedaAjustes(q){ const cont = document.getElementById('res-ajustes'); document.getElementById('barra-masiva').style.display = 'none'; if(!q || q.trim().length === 0) { cont.innerHTML = ''; return; } const res = await fetch('/buscar?q=' + encodeURIComponent(q)); itemsAjusteCache = await res.json(); cont.innerHTML = ''; itemsAjusteCache.forEach((p, idx) => { let imgHtml = p.imagen ? `<img src="/fotos-locales/${p.imagen}" style="width: 45px; height: 45px; object-fit: cover; border-radius: 10px; margin-right: 15px; border: 1px solid #e2e8f0;">` : `<div class="bg-light text-muted d-flex justify-content-center align-items-center rounded-3 border" style="width: 45px; height: 45px; margin-right: 15px;"><i class="bi bi-box fs-5"></i></div>`; cont.innerHTML += '<div class="card-pro mb-2 px-3 py-2 border-start border-4 border-primary d-flex flex-row align-items-center shadow-sm" style="cursor:pointer;"><div class="pe-3"><input class="form-check-input chk-ajuste border-secondary" type="checkbox" style="width: 22px; height: 22px; cursor:pointer;" value="' + p.CodigoProducto + '" onclick="event.stopPropagation(); actualizarBarraMasiva();"></div><div class="flex-grow-1 d-flex align-items-center" onclick="abrirModalIndividual(' + idx + ')">' + imgHtml + '<div><div class="fw-bold text-dark" style="font-size:0.95rem;">' + p.Descripcion + '</div><div class="text-muted mt-1" style="font-size:0.8rem;"><i class="bi bi-box-seam text-success"></i> <b class="text-dark">' + (p.Existencia||0) + '</b> ' + (p.Unidad||'PZ') + ' &nbsp;|&nbsp; <i class="bi bi-currency-dollar text-primary"></i> <b class="text-dark">' + parseFloat(p.Precio||0).toFixed(2) + '</b></div></div></div></div>'; }); }
            function actualizarBarraMasiva() { let seleccionados = document.querySelectorAll('.chk-ajuste:checked').length; const barra = document.getElementById('barra-masiva'); if(seleccionados > 0) { document.getElementById('count-seleccionados').innerText = seleccionados; barra.style.display = 'flex'; } else { barra.style.display = 'none'; } }
            function abrirModalMasivo() { document.getElementById('masivo-pre').value = ''; document.getElementById('masivo-stock').value = ''; document.getElementById('modalMasivo').style.display = 'flex'; }
            async function guardarMasivo() { let seleccionados = Array.from(document.querySelectorAll('.chk-ajuste:checked')).map(cb => cb.value); let pre = document.getElementById('masivo-pre').value; let stock = document.getElementById('masivo-stock').value; if(!pre && !stock) { alert('Ingresa Precio o Stock nuevo.'); return; } const res = await fetch('/actualizar-masivo', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({codigos: seleccionados, pre: pre, stock: stock}) }); if(res.ok) { alert('¡Actualizados localmente!'); document.getElementById('modalMasivo').style.display = 'none'; ejecutarBusquedaAjustes(document.getElementById('bus-ajustes').value); } }
            function abrirModalIndividual(idx) { let p = itemsAjusteCache[idx]; document.getElementById('ind-cod').value = p.CodigoProducto; document.getElementById('ind-desc').value = p.Descripcion; document.getElementById('ind-pre').value = parseFloat(p.Precio || 0).toFixed(2); document.getElementById('ind-costo').value = parseFloat(p.Costo || 0).toFixed(2); document.getElementById('ind-stock').value = p.Existencia || 0; document.getElementById('ind-iva').value = p.IVA || 0; document.getElementById('ind-unidad').value = p.Unidad || 'PZ'; document.getElementById('ind-p2').value = parseFloat(p.Precio_2 || 0).toFixed(2); document.getElementById('ind-cp2').value = parseFloat(p.Cant_P2 || 0); document.getElementById('ind-p3').value = parseFloat(p.Precio_3 || 0).toFixed(2); document.getElementById('ind-cp3').value = parseFloat(p.Cant_P3 || 0); document.getElementById('ind-pe').value = parseFloat(p.Precio_Especial || 0).toFixed(2); window.prodEdicion = { marca: p.Marca || '', prov: p.Proveedor || '', almacen: p.Almacen || '' }; document.getElementById('modalIndividual').style.display = 'flex'; }
            async function guardarIndividual() { const foto = document.getElementById('ind-foto').files[0]; const formData = new FormData(); formData.append('cod', document.getElementById('ind-cod').value); formData.append('desc', document.getElementById('ind-desc').value); formData.append('pre', parseFloat(document.getElementById('ind-pre').value) || 0); formData.append('costo', parseFloat(document.getElementById('ind-costo').value) || 0); formData.append('iva', parseFloat(document.getElementById('ind-iva').value) || 0); formData.append('unidad', document.getElementById('ind-unidad').value || 'PZ'); formData.append('stock', parseFloat(document.getElementById('ind-stock').value) || 0); formData.append('p2', parseFloat(document.getElementById('ind-p2').value) || 0); formData.append('cp2', parseFloat(document.getElementById('ind-cp2').value) || 0); formData.append('p3', parseFloat(document.getElementById('ind-p3').value) || 0); formData.append('cp3', parseFloat(document.getElementById('ind-cp3').value) || 0); formData.append('pe', parseFloat(document.getElementById('ind-pe').value) || 0); formData.append('marca', window.prodEdicion ? window.prodEdicion.marca : ''); formData.append('prov', window.prodEdicion ? window.prodEdicion.prov : ''); formData.append('almacen', window.prodEdicion ? window.prodEdicion.almacen : ''); if(foto) formData.append('foto', foto); if(!formData.get('desc')) { alert("La descripción es obligatoria."); return; } const res = await fetch('/actualizar-completo', { method: 'POST', body: formData }); if(res.ok) { alert('¡Ficha y foto actualizadas!'); document.getElementById('modalIndividual').style.display = 'none'; document.getElementById('ind-foto').value = ''; ejecutarBusquedaAjustes(document.getElementById('bus-ajustes').value); } }
            async function borrarProductoDefinitivo(cod) { if(!confirm('¿Estás seguro de ELIMINAR COMPLETAMENTE este producto? Esta acción no se puede deshacer.')) return; const res = await fetch('/borrar-producto/' + encodeURIComponent(cod), { method: 'POST' }); if(res.ok) { alert('🗑️ Producto eliminado exitosamente.'); document.getElementById('modalIndividual').style.display = 'none'; ejecutarBusquedaAjustes(document.getElementById('bus-ajustes').value); } else { alert('Error al eliminar el producto.'); } }
            
            async function guardarConfigSistem() { 
                const datos = {
                    // Aquí atrapamos el logo
                    logo: document.getElementById('cfg-logo') ? document.getElementById('cfg-logo').value : "", 
                    razon_social: document.getElementById('cfg-razon').value, 
                    rfc_empresa: document.getElementById('cfg-rfc').value, 
                    direccion_empresa: document.getElementById('cfg-dir').value, 
                    telefono_empresa: document.getElementById('cfg-tel').value, 
                    mensaje_ticket: document.getElementById('cfg-msg').value 
                }; 
                
                const res = await fetch('/guardar-config-ticket', { 
                    method: 'POST', 
                    headers: {'Content-Type': 'application/json'}, 
                    body: JSON.stringify(datos) 
                }); 
                
                if(res.ok) alert("✅ ¡Datos guardados!"); 
            }

            function cerrarSesion(){ fetch('/logout', {method: 'POST'}).then(()=>location.reload()); }
        </script>
    </body>
    </html>
    <div id="modal-alerta-esc" style="display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.85); z-index: 9999; text-align: center; padding-top: 15%;">
    <div style="background: #16191f; padding: 40px; border-radius: 10px; display: inline-block; border: 2px solid #facc15; box-shadow: 0 0 20px rgba(250, 204, 21, 0.4);">
        <h2 style="color: #facc15; font-weight: bold;">⚠️ ¿Deseas cancelar la venta?</h2>
        <h4 style="color: #f3f4f6; margin-top: 20px;">Presiona <span class="badge bg-danger">ESC</span> para CANCELAR todo.</h4>
        <h4 style="color: #f3f4f6; margin-bottom: 20px;">Presiona <span class="badge bg-success">ENTER</span> para CONTINUAR cobrando.</h4>
    </div>
</div>
    """
        
    html_content = html_content.replace("{EMPRESA_MOSTRADA}", nombre_comercial)
    html_content = html_content.replace("{USER_NAME}", safe_user_name)
    html_content = html_content.replace("{BADGE_ROL}", badge_rol)
    html_content = html_content.replace("{BTN_TALLER}", btn_t)
    html_content = html_content.replace("{BTN_DTF}", btn_dtf)
    html_content = html_content.replace("{CHK_TALLER}", chk_t)
    html_content = html_content.replace("{TXT_LABEL_CAT}", txt_label_cat)
    html_content = html_content.replace("{TXT_PLACEHOLDER_CAT}", txt_placeholder_cat)
    html_content = html_content.replace("{ADMIN_NAV_STYLE}", admin_nav_style)
    html_content = html_content.replace("{ADMIN_BLOCK_STYLE}", admin_block_style)
    html_content = html_content.replace("{USA_CADUCIDAD}", usa_caducidad)
    html_content = html_content.replace("{USER_ROLE}", safe_user_role)
    html_content = html_content.replace("{RS_E}", r_social)
    html_content = html_content.replace("{RFC_E}", rfc_e)
    html_content = html_content.replace("{DIR_E}", dir_e)
    html_content = html_content.replace("{TEL_E}", tel_e)
    html_content = html_content.replace("{MSG_E}", msg_e)
    html_content = html_content.replace("{LOGO_E}", logo_e)
    return HTMLResponse(content=html_content) 

@app.post("/auth-master")
def auth_master(response: Response, data: dict = Body(...)):
    conn = sqlite3.connect(MASTER_DB); cur = conn.cursor()
    cur.execute("SELECT nombre FROM super_usuarios WHERE nombre = ? AND pin = ?", (data['u'], data['p']))
    user = cur.fetchone(); conn.close()
    if user: response.set_cookie(key="user_role", value="superadmin", httponly=True); return {"ok": True}
    raise HTTPException(status_code=401)

@app.get("/master/empresas")
def get_empresas(user_role: Optional[str] = Cookie(None)):
    if user_role != "superadmin": raise HTTPException(403)
    conn = sqlite3.connect(MASTER_DB); conn.row_factory = sqlite3.Row; res = conn.execute("SELECT * FROM empresas ORDER BY id DESC").fetchall(); conn.close(); return [dict(row) for row in res]

@app.post("/master/crear-empresa")
def crear_empresa(bg_tasks: BackgroundTasks, data: dict = Body(...), user_role: Optional[str] = Cookie(None)):
    if user_role != "superadmin": raise HTTPException(403)
    nombre = data.get('n', '').strip(); db_alias = "".join(c for c in nombre if c.isalnum()).lower()
    giro = data.get('g', 'general')
    conn_m = sqlite3.connect(MASTER_DB); cur_m = conn_m.cursor()
    cur_m.execute("SELECT id FROM empresas WHERE db_alias = ?", (db_alias,))
    if cur_m.fetchone(): conn_m.close(); return {"ok": False, "msg": "Esta empresa ya existe."}
    fecha = datetime.now().strftime("%Y-%m-%d")
    cur_m.execute("INSERT INTO empresas (nombre_comercial, db_alias, fecha_creacion, giro) VALUES (?, ?, ?, ?)", (nombre, db_alias, fecha, giro)); conn_m.commit(); conn_m.close()
    ruta_db = get_db_path(db_alias); inicializar_db(ruta_db); conn_s = sqlite3.connect(ruta_db)
    conn_s.execute("INSERT INTO usuarios (nombre, pin, rol) VALUES (?, ?, 'admin')", (data['u'], data['p']))
    usa_fracciones = "1" if giro in ["ferreteria", "abarrotes"] else "0"
    usa_caducidad = "1" if giro in ["farmacia", "abarrotes"] else "0"
    usa_taller = "1" if giro in ["impresion", "ferreteria"] else "0"
    conn_s.execute("INSERT OR REPLACE INTO configuracion (parametro, valor) VALUES ('usa_fracciones', ?)", (usa_fracciones,))
    conn_s.execute("INSERT OR REPLACE INTO configuracion (parametro, valor) VALUES ('usa_caducidad', ?)", (usa_caducidad,))
    conn_s.execute("INSERT OR REPLACE INTO configuracion (parametro, valor) VALUES ('usa_taller', ?)", (usa_taller,))
    conn_s.commit(); conn_s.close()
    bg_tasks.add_task(sync_to_supabase, "empresas", {"nombre_comercial": nombre, "db_alias": db_alias, "fecha_creacion": fecha, "giro": giro})
    bg_tasks.add_task(sync_to_supabase, "usuarios", {"empresa_id": db_alias, "nombre": data['u'], "pin": data['p'], "rol": 'admin'})
    return {"ok": True}

@app.post("/auth")
def autenticar(response: Response, data: dict = Body(...)):
    negocio_real = data.get('n', '').strip()
    if not negocio_real or not data.get('u') or not data.get('p'): return {"ok": False, "msg": "Faltan datos."}
    db_alias = "".join(c for c in negocio_real if c.isalnum()).lower(); ruta_db = get_db_path(db_alias)
    if not os.path.exists(ruta_db) or os.path.getsize(ruta_db) == 0: return {"ok": False, "msg": "Empresa no encontrada en la PC."}
    try:
        conn = sqlite3.connect(ruta_db); conn.row_factory = sqlite3.Row; cur = conn.cursor()
        cur.execute("SELECT nombre, rol FROM usuarios WHERE nombre = ? AND pin = ?", (data['u'], data['p']))
        user = cur.fetchone(); conn.close()
    except Exception as e: return {"ok": False, "msg": "Error BD."}
    if not user: return {"ok": False, "msg": "Credenciales incorrectas."}
    response.set_cookie(key="user_role", value=user['rol'], httponly=True); response.set_cookie(key="user_name", value=user['nombre'], httponly=True)
    response.set_cookie(key="user_business_id", value=db_alias, httponly=True); response.set_cookie(key="user_business_name", value=urllib.parse.quote(negocio_real), httponly=True)
    return {"ok": True}

@app.post("/vender")
def vender(bg_tasks: BackgroundTasks, payload: dict = Body(...), user_name: Optional[str] = Cookie(None), user_business_id: Optional[str] = Cookie(None), user_business_name: Optional[str] = Cookie(None)):
    if not user_business_id: raise HTTPException(401)
    items, pago, es_anticipo = payload['items'], payload['pago'], payload['es_anticipo']
    cliente, total_v, metodo = payload['cliente'], payload['total'], payload.get('metodo', 'EFECTIVO')
    en_taller = payload.get('en_taller', False); cajero_actual = user_name or "SISTEMA"
    link_archivo = payload.get('link_archivo', '')
    puntos_usados = float(payload.get('puntos_usados', 0))
    tipo_deuda = payload.get('tipo_deuda', 'CREDITO')
    
    total_despues_puntos = total_v 
    if total_despues_puntos < 0: total_despues_puntos = 0
    
    ahora = datetime.now(); f = ahora.strftime("%Y-%m-%d"); h = ahora.strftime("%H:%M:%S")
    estado = tipo_deuda if es_anticipo else "COMPLETADA"; estado_prod = "FILA" if en_taller else "ENTREGADO"
    
    resta = (total_despues_puntos - pago) if es_anticipo else 0
    if resta < 0: resta = 0
    dinero_caja = pago if es_anticipo else total_despues_puntos
    if dinero_caja > total_despues_puntos: dinero_caja = total_despues_puntos
    if dinero_caja < 0: dinero_caja = 0
    
    nombre_comercial = urllib.parse.unquote(user_business_name).upper() if user_business_name else "MI NEGOCIO"
    ticket = f"*{nombre_comercial} - COMPROBANTE*\nCliente: {cliente}\nTotal: ${total_despues_puntos:.2f}\nMétodo: {metodo}\nCajero: {cajero_actual}\n" + (f"ANTICIPO: ${pago:.2f}\n*RESTA: ${resta:.2f}*" if es_anticipo else f"PAGADO: ${pago:.2f}")
    
    conn = conectar(user_business_id); cur = conn.cursor()
    cur.execute("INSERT INTO ventas (fecha, total, cliente, estado, saldo_pendiente, cajero, estado_produccion, link_archivo) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (f"{f} {h}", total_despues_puntos, cliente, estado, resta, cajero_actual, estado_prod, link_archivo)); v_id = cur.lastrowid
    bg_tasks.add_task(sync_to_supabase, "ventas", {"id": v_id, "empresa_id": user_business_id, "fecha": f"{f} {h}", "total": total_despues_puntos, "cliente": cliente, "estado": estado, "saldo_pendiente": resta, "cajero": cajero_actual, "estado_produccion": estado_prod, "link_archivo": link_archivo})
    
    if dinero_caja > 0: 
        cur.execute("INSERT INTO abonos (id_venta, fecha, monto, cajero, metodo) VALUES (?, ?, ?, ?, ?)", (v_id, f"{f} {h}", dinero_caja, cajero_actual, metodo))
        bg_tasks.add_task(sync_to_supabase, "abonos", {"empresa_id": user_business_id, "id_venta": v_id, "fecha": f"{f} {h}", "monto": dinero_caja, "cajero": cajero_actual, "metodo": metodo})
        
    for i in items:
        cur.execute("INSERT INTO ventas_detalle (id_venta, fecha, hora, codigo, descripcion, cantidad, total_cobrado, metodo_pago) VALUES (?,?,?,?,?,?,?,?)", (v_id, f, h, i['cod'], i['desc'], i['cant'], i['pre']*i['cant'], metodo))
        bg_tasks.add_task(sync_to_supabase, "ventas_detalle", {"empresa_id": user_business_id, "id_venta": v_id, "fecha": f, "hora": h, "codigo": i['cod'], "descripcion": i['desc'], "cantidad": i['cant'], "total_cobrado": i['pre']*i['cant'], "metodo_pago": metodo})
        
        if not str(i['cod']).startswith("TEMP") and not str(i['cod']).startswith("SRV-"): 
            cur.execute("UPDATE productos SET Existencia = Existencia - ? WHERE CodigoProducto = ?", (i['cant'], i['cod']))
            cur.execute("SELECT Existencia FROM productos WHERE CodigoProducto = ?", (i['cod'],)); n_stock = cur.fetchone()[0]
            bg_tasks.add_task(sync_update_supabase, "productos", {"Existencia": n_stock}, "CodigoProducto", i['cod'], user_business_id)
    
    if cliente and cliente not in ["Cliente de Mostrador", "GENERAL"]:
        puntos_ganados = total_despues_puntos * 0.05
        try:
            cur.execute("INSERT INTO clientes (nombre, fecha_registro, puntos) VALUES (?, ?, ?)", (cliente, f, puntos_ganados))
            bg_tasks.add_task(sync_to_supabase, "clientes", {"empresa_id": user_business_id, "nombre": cliente, "fecha_registro": f, "puntos": puntos_ganados})
        except sqlite3.IntegrityError:
            cur.execute("UPDATE clientes SET puntos = puntos - ? + ? WHERE nombre = ?", (puntos_usados, puntos_ganados, cliente))
            cur.execute("SELECT puntos FROM clientes WHERE nombre = ?", (cliente,)); pts_act = cur.fetchone()[0]
            bg_tasks.add_task(sync_update_supabase, "clientes", {"puntos": pts_act}, "nombre", cliente, user_business_id)

    conn.commit(); conn.close(); return {"ok": True, "mensaje_whatsapp": ticket}

@app.get("/clientes")
def get_clientes(user_role: Optional[str] = Cookie(None), user_business_id: Optional[str] = Cookie(None)):
    if not user_role or not user_business_id: raise HTTPException(401)
    conn = conectar(user_business_id); conn.row_factory = sqlite3.Row; res = conn.execute("SELECT * FROM clientes ORDER BY nombre ASC").fetchall(); conn.close(); return [dict(row) for row in res]

@app.post("/nuevo-cliente")
def nuevo_cliente(bg_tasks: BackgroundTasks, data: dict = Body(...), user_role: Optional[str] = Cookie(None), user_business_id: Optional[str] = Cookie(None)):
    if not user_role or not user_business_id: raise HTTPException(401)
    conn = conectar(user_business_id); cur = conn.cursor(); fecha = datetime.now().strftime("%Y-%m-%d")
    try: cur.execute("INSERT INTO clientes (nombre, telefono, correo, fecha_registro) VALUES (?, ?, ?, ?)", (data['nombre'], data.get('tel', ''), data.get('correo', ''), fecha)); conn.commit(); bg_tasks.add_task(sync_to_supabase, "clientes", {"empresa_id": user_business_id, "nombre": data['nombre'], "telefono": data.get('tel', ''), "correo": data.get('correo', ''), "fecha_registro": fecha}); return {"ok": True}
    except sqlite3.IntegrityError: return {"ok": False, "msg": "Ese cliente ya existe."}
    finally: conn.close()

@app.post("/borrar-cliente/{nombre_cliente}")
def borrar_cliente(bg_tasks: BackgroundTasks, nombre_cliente: str, user_role: Optional[str] = Cookie(None), user_business_id: Optional[str] = Cookie(None)):
    if user_role != "admin" or not user_business_id: raise HTTPException(403)
    conn = conectar(user_business_id); cur = conn.cursor()
    cur.execute("SELECT SUM(saldo_pendiente) FROM ventas WHERE cliente = ?", (nombre_cliente,))
    deuda = cur.fetchone()[0]
    if deuda and deuda > 0:
        conn.close()
        return {"ok": False, "msg": f"⚠️ No se puede eliminar. El cliente aún debe ${deuda:.2f}."}
    cur.execute("DELETE FROM clientes WHERE nombre = ?", (nombre_cliente,))
    conn.commit(); conn.close()
    bg_tasks.add_task(sync_delete_supabase, "clientes", "nombre", nombre_cliente, user_business_id)
    return {"ok": True}

@app.get("/historial-cliente")
def historial_cliente(nombre: str, user_role: Optional[str] = Cookie(None), user_business_id: Optional[str] = Cookie(None)):
    if not user_role or not user_business_id: raise HTTPException(401)
    conn = conectar(user_business_id); cur = conn.cursor()
    cur.execute("SELECT SUM(saldo_pendiente) as deuda FROM ventas WHERE cliente = ? AND estado IN ('PENDIENTE', 'CREDITO', 'APARTADO')", (nombre,)); fila_deuda = cur.fetchone(); deuda = fila_deuda['deuda'] if fila_deuda and fila_deuda['deuda'] else 0.0
    cur.execute("SELECT id, fecha, total, estado, saldo_pendiente FROM ventas WHERE cliente = ? ORDER BY id DESC LIMIT 10", (nombre,)); ventas = cur.fetchall(); conn.close(); return {"pendientes": deuda, "ventas": [dict(v) for v in ventas]}

@app.get("/pedidos-taller")
def pedidos_taller(user_role: Optional[str] = Cookie(None), user_business_id: Optional[str] = Cookie(None)):
    if not user_role or not user_business_id: raise HTTPException(401)
    conn = conectar(user_business_id); cur = conn.cursor()
    cur.execute("SELECT v.id, v.cliente, v.estado_produccion, c.telefono FROM ventas v LEFT JOIN clientes c ON v.cliente = c.nombre WHERE v.estado_produccion IN ('FILA', 'PRODUCCION', 'LISTO') ORDER BY v.id ASC")
    ventas_taller = cur.fetchall(); resultados = []
    for v in ventas_taller: cur.execute("SELECT descripcion, cantidad FROM ventas_detalle WHERE id_venta = ?", (v['id'],)); detalles = cur.fetchall(); resultados.append({ "id": v['id'], "cliente": v['cliente'], "estado_produccion": v['estado_produccion'], "telefono": v['telefono'], "items": [{"descripcion": d['descripcion'], "cantidad": d['cantidad']} for d in detalles] })
    conn.close(); return resultados

@app.post("/actualizar-taller")
def actualizar_taller(bg_tasks: BackgroundTasks, payload: dict = Body(...), user_role: Optional[str] = Cookie(None), user_business_id: Optional[str] = Cookie(None)):
    if not user_role or not user_business_id: raise HTTPException(401)
    conn = conectar(user_business_id); cur = conn.cursor(); cur.execute("UPDATE ventas SET estado_produccion = ? WHERE id = ?", (payload.get('estado'), payload.get('id'))); conn.commit(); conn.close()
    bg_tasks.add_task(sync_update_supabase, "ventas", {"estado_produccion": payload.get('estado')}, "id", payload.get('id'), user_business_id); return {"ok": True}

@app.post("/fondo-caja")
def fondo_caja(payload: dict = Body(...), user_name: Optional[str] = Cookie(None), user_business_id: Optional[str] = Cookie(None)):
    if not user_business_id: raise HTTPException(401)
    f = datetime.now().strftime("%Y-%m-%d %H:%M:%S"); cajero = user_name or "SISTEMA"
    conn = conectar(user_business_id); conn.execute("INSERT INTO fondo_caja (fecha, monto, cajero) VALUES (?, ?, ?)", (f, payload['monto'], cajero))
    conn.commit(); conn.close(); return {"ok": True}

@app.get("/mi-turno")
def mi_turno(user_role: Optional[str] = Cookie(None), user_name: Optional[str] = Cookie(None), user_business_id: Optional[str] = Cookie(None)):
    if not user_business_id or not user_name: raise HTTPException(403)
    f = datetime.now().strftime("%Y-%m-%d"); conn = conectar(user_business_id); cur = conn.cursor()
    cur.execute("SELECT SUM(monto) as total FROM abonos WHERE fecha LIKE ? AND cajero = ? AND metodo = 'EFECTIVO'", (f"{f}%", user_name)); efe = cur.fetchone()['total'] or 0.0
    cur.execute("SELECT SUM(monto) as total FROM abonos WHERE fecha LIKE ? AND cajero = ? AND metodo != 'EFECTIVO'", (f"{f}%", user_name)); tar = cur.fetchone()['total'] or 0.0
    cur.execute("SELECT SUM(monto) as total FROM gastos WHERE fecha LIKE ? AND cajero = ?", (f"{f}%", user_name)); gas = cur.fetchone()['total'] or 0.0
    cur.execute("SELECT SUM(monto) as total FROM fondo_caja WHERE fecha LIKE ? AND cajero = ?", (f"{f}%", user_name)); fondo = cur.fetchone()['total'] or 0.0
    conn.close(); return {"efectivo": efe, "tarjeta": tar, "gastos": gas, "fondo": fondo, "cajon": fondo + efe - gas}

@app.post("/generar-reporte")
def generar_reporte(data: dict = Body(...), user_role: Optional[str] = Cookie(None), user_business_id: Optional[str] = Cookie(None)):
    if user_role != "admin" or not user_business_id: raise HTTPException(status_code=403)
    f_inicio = data.get('inicio', datetime.now().strftime("%Y-%m-%d"))
    f_fin = data.get('fin', datetime.now().strftime("%Y-%m-%d"))
    cajero_filtro = data.get('cajero', 'TODOS')
    conn = conectar(user_business_id); conn.row_factory = sqlite3.Row; cur = conn.cursor()
    
    query = "SELECT vd.fecha, vd.hora, vd.codigo, vd.descripcion, vd.cantidad, vd.total_cobrado, (vd.total_cobrado - (COALESCE(p.Costo, 0) * vd.cantidad)) as ganancia, vd.metodo_pago, v.cajero FROM ventas_detalle vd LEFT JOIN productos p ON vd.codigo = p.CodigoProducto LEFT JOIN ventas v ON vd.id_venta = v.id WHERE vd.fecha BETWEEN ? AND ?"
    params = [f_inicio, f_fin]
    if cajero_filtro != 'TODOS':
        query += " AND v.cajero = ?"; params.append(cajero_filtro)
    try: cur.execute(query, params); datos_v = cur.fetchall()
    except: datos_v = []

    query_g = "SELECT fecha, descripcion, monto, cajero FROM gastos WHERE date(fecha) BETWEEN ? AND ?"
    params_g = [f_inicio, f_fin]
    if cajero_filtro != 'TODOS':
        query_g += " AND cajero = ?"; params_g.append(cajero_filtro)
    try: cur.execute(query_g, params_g); datos_g = cur.fetchall()
    except: datos_g = []

    conn.close()
    t_vta = 0.0; t_util = 0.0; t_items = 0; s_efe = 0.0; s_tar = 0.0; lista = []
    for d in datos_v:
        vta = float(d['total_cobrado']) if d['total_cobrado'] else 0.0; util = float(d['ganancia']) if d['ganancia'] else 0.0; met = str(d['metodo_pago']).upper() if d['metodo_pago'] else "EFECTIVO"
        caj = str(d['cajero']).upper() if 'cajero' in d.keys() and d['cajero'] else "SISTEMA"; t_vta += vta; t_util += util; t_items += int(d['cantidad'])
        if met == "TRANSFERENCIA": s_tar += vta
        else: s_efe += vta
        lista.append({"tipo": "venta", "fecha": str(d['fecha']), "hora": str(d['hora']), "codigo": str(d['codigo']), "desc": str(d['descripcion']), "cant": int(d['cantidad']), "metodo": met, "total": vta, "cajero": caj})
        
    for g in datos_g:
        fecha_str = str(g['fecha'])
        f_only = fecha_str.split(" ")[0] if " " in fecha_str else fecha_str
        h_only = fecha_str.split(" ")[1] if " " in fecha_str else "00:00:00"
        lista.append({"tipo": "retiro", "fecha": f_only, "hora": h_only, "codigo": "RETIRO", "desc": str(g['descripcion']), "cant": "-", "metodo": "EFECTIVO", "total": float(g['monto']), "cajero": str(g['cajero'])})
        
    lista.sort(key=lambda x: (x['fecha'], x['hora']), reverse=True)
    return {"total_ventas": t_vta, "total_utilidad": t_util, "total_items": t_items, "suma_efectivo": s_efe, "suma_transferencia": s_tar, "detalle": lista}

@app.get("/lista-compras")
def lista_compras(user_role: Optional[str] = Cookie(None), user_business_id: Optional[str] = Cookie(None)):
    if user_role != "admin" or not user_business_id: raise HTTPException(403)
    conn = conectar(user_business_id); res = conn.execute("SELECT CodigoProducto, Descripcion, Existencia, Proveedor, Prov_WhatsApp FROM productos WHERE Existencia <= 5 ORDER BY Proveedor ASC, Existencia ASC").fetchall(); conn.close(); return [dict(row) for row in res]

@app.get("/buscar")
def buscar(q: str, user_role: Optional[str] = Cookie(None), user_business_id: Optional[str] = Cookie(None)):
    if not user_role or not user_business_id: raise HTTPException(status_code=401)
    conn = conectar(user_business_id); conn.row_factory = sqlite3.Row; termino = f'%{q}%'
    try: res = conn.execute("SELECT * FROM productos WHERE Descripcion LIKE ? OR CodigoProducto LIKE ? LIMIT 150", (termino, termino)).fetchall()
    except: res = conn.execute("SELECT CodigoProducto, Descripcion, Precio, Existencia FROM productos WHERE Descripcion LIKE ? OR CodigoProducto LIKE ? LIMIT 150", (termino, termino)).fetchall()
    conn.close(); return [dict(row) for row in res]

@app.post("/nuevo-producto")
async def nuevo_producto(bg_tasks: BackgroundTasks, cod: str = Form(...), desc: str = Form(...), cat: str = Form(""), fecha: str = Form(""), pre: float = Form(0), costo: float = Form(0), stock: float = Form(0), prov: str = Form(""), wa: str = Form(""), mail: str = Form(""), caducidad: str = Form(""), unidad: str = Form("PZ"), p2: float = Form(0), cp2: float = Form(0), p3: float = Form(0), cp3: float = Form(0), pe: float = Form(0), foto: Optional[UploadFile] = File(None), user_role: Optional[str] = Cookie(None), user_business_id: Optional[str] = Cookie(None)):
    if user_role != "admin" or not user_business_id: raise HTTPException(403)
    conn = conectar(user_business_id); cur = conn.cursor()
    cur.execute("SELECT CodigoProducto, Descripcion, Precio, Existencia FROM productos WHERE CodigoProducto = ? OR Descripcion = ?", (cod, desc)); prod_ex = cur.fetchone()
    if prod_ex: conn.close(); return {"ok": False, "duplicado": True, "prod": dict(prod_ex)}
    fecha_captura = datetime.now().strftime("%Y-%m-%d %H:%M:%S"); fe = fecha if str(fecha).strip() != "" else None; nombre_imagen = None
    if foto and foto.filename: ext = os.path.splitext(foto.filename)[1]; nombre_imagen = f"prod_{cod}{ext}"; ruta_local = os.path.join(FOTOS_DIR, nombre_imagen); bg_tasks.add_task(sync_foto_supabase, ruta_local, nombre_imagen)
    try:
        cur.execute("""INSERT INTO productos (CodigoProducto, Descripcion, Precio, Costo, Existencia, FechaCaptura, Categoria, FechaEntrada, Proveedor, Prov_WhatsApp, Prov_Mail, imagen, Caducidad, Unidad, Precio_2, Cant_P2, Precio_3, Cant_P3, Precio_Especial) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (cod, desc, pre, costo, stock, fecha_captura, cat, fe, prov, wa, mail, nombre_imagen, caducidad, unidad, p2, cp2, p3, cp3, pe)); conn.commit()
        datos_nube = { "empresa_id": user_business_id, "CodigoProducto": cod, "Descripcion": desc, "Precio": pre, "Costo": costo, "Existencia": stock, "FechaCaptura": fecha_captura, "Categoria": cat, "FechaEntrada": fe, "Proveedor": prov, "Prov_WhatsApp": wa, "Prov_Mail": mail, "imagen": nombre_imagen, "Caducidad": caducidad, "Unidad": unidad, "Precio_2": p2, "Cant_P2": cp2, "Precio_3": p3, "Cant_P3": cp3, "Precio_Especial": pe }
        bg_tasks.add_task(sync_to_supabase, "productos", datos_nube); return {"ok": True}
    except Exception as e: return {"ok": False, "msg": f"Error base local: {str(e)}"}
    finally: conn.close()

@app.post("/actualizar-masivo")
def actualizar_masivo(bg_tasks: BackgroundTasks, data: dict = Body(...), user_role: Optional[str] = Cookie(None), user_business_id: Optional[str] = Cookie(None)):
    if user_role != "admin" or not user_business_id: raise HTTPException(403)
    codigos = data.get('codigos', []); pre = data.get('pre', ""); stock = data.get('stock', "")
    if not codigos: return {"ok": False, "msg": "Sin selección"}
    conn = conectar(user_business_id); cur = conn.cursor()
    try:
        for cod in codigos:
            updates = {}
            if pre != "": cur.execute("UPDATE productos SET Precio = ? WHERE CodigoProducto = ?", (float(pre), cod)); updates["Precio"] = float(pre)
            if stock != "": cur.execute("UPDATE productos SET Existencia = ? WHERE CodigoProducto = ?", (float(stock), cod)); updates["Existencia"] = float(stock)
            if updates: bg_tasks.add_task(sync_update_supabase, "productos", updates, "CodigoProducto", cod, user_business_id)
        conn.commit(); return {"ok": True}
    finally: conn.close()

@app.post("/actualizar-completo")
async def actualizar_completo(bg_tasks: BackgroundTasks, cod: str = Form(...), desc: str = Form(...), pre: float = Form(0), costo: float = Form(0), iva: float = Form(0), unidad: str = Form("PZ"), stock: float = Form(0), p2: float = Form(0), cp2: float = Form(0), p3: float = Form(0), cp3: float = Form(0), pe: float = Form(0), marca: str = Form(""), prov: str = Form(""), almacen: str = Form(""), foto: Optional[UploadFile] = File(None), user_role: Optional[str] = Cookie(None), user_business_id: Optional[str] = Cookie(None)):
    if user_role != "admin" or not user_business_id: raise HTTPException(403)
    conn = conectar(user_business_id); cur = conn.cursor(); nombre_imagen = None
    if foto and foto.filename: ext = os.path.splitext(foto.filename)[1]; nombre_imagen = f"prod_{cod}{ext}"; ruta_local = os.path.join(FOTOS_DIR, nombre_imagen); bg_tasks.add_task(sync_foto_supabase, ruta_local, nombre_imagen)
    try:
        if nombre_imagen: cur.execute("UPDATE productos SET Descripcion=?, Precio=?, Costo=?, IVA=?, Unidad=?, Existencia=?, Marca=?, Proveedor=?, Almacen=?, imagen=?, Precio_2=?, Cant_P2=?, Precio_3=?, Cant_P3=?, Precio_Especial=? WHERE CodigoProducto=?", (desc, pre, costo, iva, unidad, stock, marca, prov, almacen, nombre_imagen, p2, cp2, p3, cp3, pe, cod))
        else: cur.execute("UPDATE productos SET Descripcion=?, Precio=?, Costo=?, IVA=?, Unidad=?, Existencia=?, Marca=?, Proveedor=?, Almacen=?, Precio_2=?, Cant_P2=?, Precio_3=?, Cant_P3=?, Precio_Especial=? WHERE CodigoProducto=?", (desc, pre, costo, iva, unidad, stock, marca, prov, almacen, p2, cp2, p3, cp3, pe, cod))
        conn.commit()
        return {"ok": True}
    finally: conn.close()

@app.post("/nueva-promocion")
def nueva_promocion(bg_tasks: BackgroundTasks, data: dict = Body(...), user_role: Optional[str] = Cookie(None), user_business_id: Optional[str] = Cookie(None)):
    if user_role != "admin" or not user_business_id: raise HTTPException(403)
    conn = conectar(user_business_id); cur = conn.cursor(); ini = data.get('inicio', ''); fin = data.get('fin', '')
    if not ini or str(ini).strip() == "": ini = None
    if not fin or str(fin).strip() == "": fin = None
    cur.execute("INSERT INTO promociones (codigo_producto, cantidad_requerida, precio_promocional, fecha_inicio, fecha_fin) VALUES (?, ?, ?, ?, ?)", (data['codigo'], data['cant'], data['precio'], ini, fin)); promo_id = cur.lastrowid; conn.commit(); conn.close()
    return {"ok": True}

@app.get("/lista-promociones")
def lista_promociones(user_business_id: Optional[str] = Cookie(None)):
    if not user_business_id: raise HTTPException(401)
    conn = conectar(user_business_id); res = conn.execute("SELECT id, codigo_producto, cantidad_requerida, precio_promocional, fecha_inicio, fecha_fin FROM promociones WHERE activa = 1").fetchall(); conn.close(); return [dict(row) for row in res]

@app.post("/borrar-promocion/{id_promo}")
def borrar_promocion(bg_tasks: BackgroundTasks, id_promo: int, user_role: Optional[str] = Cookie(None), user_business_id: Optional[str] = Cookie(None)):
    if user_role != "admin" or not user_business_id: raise HTTPException(403)
    conn = conectar(user_business_id); conn.execute("UPDATE promociones SET activa = 0 WHERE id = ?", (id_promo,)); conn.commit(); conn.close(); return {"ok": True}

@app.get("/exportar-inventario")
def exportar_inventario(user_role: Optional[str] = Cookie(None), user_business_id: Optional[str] = Cookie(None)):
    if user_role != "admin" or not user_business_id: raise HTTPException(403)
    conn = conectar(user_business_id); cur = conn.cursor(); cur.execute("SELECT CodigoProducto, Descripcion, Precio, Costo, Existencia, Proveedor, Prov_WhatsApp, Prov_Mail, Categoria, FechaEntrada, Precio_2, Cant_P2, Precio_3, Cant_P3, Precio_Especial FROM productos"); filas = cur.fetchall(); conn.close()
    output = io.StringIO(); writer = csv.writer(output); writer.writerow(["CodigoProducto", "Descripcion", "Precio", "Costo", "Existencia", "Proveedor", "WhatsApp_Prov", "Mail_Prov", "Categoria", "FechaEntrada", "Precio_2", "Cant_P2", "Precio_3", "Cant_P3", "Precio_Especial"])
    for f in filas: writer.writerow([f["CodigoProducto"], f["Descripcion"], f["Precio"], f["Costo"], f["Existencia"], f["Proveedor"], f["Prov_WhatsApp"], f["Prov_Mail"], f["Categoria"], f["FechaEntrada"], f["Precio_2"], f["Cant_P2"], f["Precio_3"], f["Cant_P3"], f["Precio_Especial"]])
    return Response(content=output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=inventario_microcom.csv"})

@app.post("/importar-inventario")
async def importar_inventario(bg_tasks: BackgroundTasks, file: UploadFile = File(...), user_role: Optional[str] = Cookie(None), user_business_id: Optional[str] = Cookie(None)):
    if user_role != "admin" or not user_business_id: raise HTTPException(403)
    contenido = await file.read()
    try: texto = contenido.decode("utf-8")
    except: texto = contenido.decode("latin-1")
    lector = csv.DictReader(io.StringIO(texto)); conn = conectar(user_business_id); cur = conn.cursor(); fecha_captura = datetime.now().strftime("%Y-%m-%d %H:%M:%S"); count = 0
    for fila in lector:
        try:
            cod = str(fila.get("CodigoProducto", "")).strip(); desc = str(fila.get("Descripcion", "")).strip()
            if not cod or not desc: continue
            pre = float(fila.get("Precio", 0) or 0); costo = float(fila.get("Costo", 0) or 0); stock = float(fila.get("Existencia", 0) or 0)
            prov = str(fila.get("Proveedor", "")).strip(); wa = str(fila.get("WhatsApp_Prov", "")).strip(); mail = str(fila.get("Mail_Prov", "")).strip(); cat = str(fila.get("Categoria", "")).strip(); fe = str(fila.get("FechaEntrada", "")).strip()
            if not fe: fe = None
            p2 = float(fila.get("Precio_2", 0) or 0); cp2 = float(fila.get("Cant_P2", 0) or 0)
            p3 = float(fila.get("Precio_3", 0) or 0); cp3 = float(fila.get("Cant_P3", 0) or 0)
            pe = float(fila.get("Precio_Especial", 0) or 0)
            cur.execute("""INSERT INTO productos (CodigoProducto, Descripcion, Precio, Costo, Existencia, FechaCaptura, Proveedor, Prov_WhatsApp, Prov_Mail, Categoria, FechaEntrada, Precio_2, Cant_P2, Precio_3, Cant_P3, Precio_Especial) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(CodigoProducto) DO UPDATE SET Descripcion=excluded.Descripcion, Precio=excluded.Precio, Costo=excluded.Costo, Existencia=excluded.Existencia, Proveedor=excluded.Proveedor, Prov_WhatsApp=excluded.Prov_WhatsApp, Prov_Mail=excluded.Prov_Mail, Categoria=excluded.Categoria, FechaEntrada=excluded.FechaEntrada, Precio_2=excluded.Precio_2, Cant_P2=excluded.Cant_P2, Precio_3=excluded.Precio_3, Cant_P3=excluded.Cant_P3, Precio_Especial=excluded.Precio_Especial""", (cod, desc, pre, costo, stock, fecha_captura, prov, wa, mail, cat, fe, p2, cp2, p3, cp3, pe)); count += 1
        except Exception: continue
    conn.commit(); conn.close(); return {"ok": True, "msg": f"¡Éxito! Se actualizaron {count} productos."}

@app.get("/equipo")
def get_equipo(user_role: Optional[str] = Cookie(None), user_business_id: Optional[str] = Cookie(None)):
    if user_role != "admin": raise HTTPException(403)
    conn = conectar(user_business_id); conn.row_factory = sqlite3.Row; res = conn.execute("SELECT id, nombre, rol FROM usuarios").fetchall(); conn.close(); return [dict(row) for row in res]

@app.post("/nuevo-miembro")
def nuevo_miembro(bg_tasks: BackgroundTasks, data: dict = Body(...), user_role: Optional[str] = Cookie(None), user_business_id: Optional[str] = Cookie(None)):
    if user_role != "admin": raise HTTPException(403)
    conn = conectar(user_business_id); cur = conn.cursor(); cur.execute("INSERT INTO usuarios (nombre, pin, rol) VALUES (?, ?, ?)", (data['u'], data['p'], data['r'])); u_id = cur.lastrowid; conn.commit(); conn.close(); return {"ok": True}

@app.post("/borrar-miembro/{u_id}")
def borrar_miembro(bg_tasks: BackgroundTasks, u_id: int, user_role: Optional[str] = Cookie(None), user_business_id: Optional[str] = Cookie(None)):
    if user_role != "admin": raise HTTPException(403)
    conn = conectar(user_business_id); cur = conn.cursor(); cur.execute("DELETE FROM usuarios WHERE id = ?", (u_id,)); conn.commit(); conn.close(); return {"ok": True}

@app.get("/leer-bascula")
def leer_bascula(user_role: Optional[str] = Cookie(None), user_business_id: Optional[str] = Cookie(None)):
    if not user_role or not user_business_id: raise HTTPException(status_code=401)
    time.sleep(0.5); peso_simulado = round(random.uniform(0.100, 3.500), 3)
    return {"ok": True, "peso": peso_simulado, "msg": f"Peso leído correctamente"}

@app.post("/borrar-producto/{cod}")
def borrar_producto(bg_tasks: BackgroundTasks, cod: str, user_role: Optional[str] = Cookie(None), user_business_id: Optional[str] = Cookie(None)):
    if user_role != "admin" or not user_business_id: raise HTTPException(403)
    conn = conectar(user_business_id); cur = conn.cursor(); cur.execute("DELETE FROM productos WHERE CodigoProducto = ?", (cod,)); conn.commit(); conn.close(); return {"ok": True}

@app.post("/logout")
def logout(response: Response): response.delete_cookie("user_role"); response.delete_cookie("user_name"); response.delete_cookie("user_business_id"); response.delete_cookie("user_business_name"); return {"ok": True}

@app.post("/sincronizar-buzon")
def sincronizar_buzon(user_business_id: Optional[str] = Cookie(None)):
    if not user_business_id: 
        return {"ok": False, "msg": "Sesión inválida."}
    
    # 1. Abrimos la conexión (Esto quita las líneas rojas de 'conn' y 'cur')
    conn = sqlite3.connect(MASTER_DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    try:
        pendientes = [dict(row) for row in cur.execute("SELECT * FROM buzon_salida WHERE empresa_id = ?", (user_business_id,)).fetchall()]
        
        if not pendientes:
            conn.close()
            return {"ok": True, "msg": "Sincronización Perfecta."}

        errores = 0
        ultimo_id_venta_nube = None 

        for p in pendientes:
            tabla = p['tabla']; operacion = p['operacion']; p_id = p['id']
            datos = json.loads(p['datos'])
            
            try:
                if operacion == 'insert':
                    # EL TRUCO MAESTRO: Borramos el ID local para que NO choque con la nube
                    if 'id' in datos: del datos['id']
                    
                    if tabla == 'ventas':
                        # Registramos el ticket y dejamos que la nube le asigne su número oficial
                        res = supabase.table('ventas').insert(datos).execute()
                        if res.data:
                            ultimo_id_venta_nube = res.data[0]['id']
                    
                    elif tabla == 'ventas_detalle' and ultimo_id_venta_nube:
                        # Amarramos el producto al número de ticket que nos dio la nube
                        datos['venta_id'] = ultimo_id_venta_nube
                        supabase.table('ventas_detalle').insert(datos).execute()
                    else:
                        supabase.table(tabla).insert(datos).execute()

                elif operacion == 'update':
                    supabase.table(tabla).update(datos).eq("empresa_id", user_business_id).eq(p['col_filtro'], p['val_filtro']).execute()
                
                elif operacion == 'delete':
                    supabase.table(tabla).delete().eq("empresa_id", user_business_id).eq(p['col_filtro'], p['val_filtro']).execute()

                # Si funcionó en la nube, lo borramos de la compu
                cur.execute("DELETE FROM buzon_salida WHERE id = ?", (p_id,))
                
            except Exception as e:
                print(f"Error en {tabla}: {e}")
                errores += 1

        conn.commit()
        conn.close() # Cerramos limpio
        
        if errores > 0:
            return {"ok": False, "msg": f"Quedaron {errores} pendientes."}
        return {"ok": True, "msg": "¡Sincronización Perfecta!"}

    except Exception as e:
        if conn: conn.close()
        return {"ok": False, "msg": str(e)}

@app.get("/matar-pendientes")
def matar_pendientes(user_business_id: str = Cookie(None)):
    # Ahora sí, esta función recibe una respuesta clara y no falla
    res = sincronizar_buzon(user_business_id)
    if not res.get("ok", False):
        return {"msg": f"Error: {res.get('msg')}"}
    return {"msg": "✅ ¡Todo subido y buzón limpio!"}
    
    # Variable para recordar el ID que nos dé la nube
    ultimo_id_venta_nube = None 

    for p in pendientes:
        tabla = p['tabla']
        operacion = p['operacion']
        p_id = p['id']
        datos = json.loads(p['datos'])
        
        try:
            if operacion == 'insert':
                if tabla == 'ventas':
                    # 1. Insertamos la cabecera y capturamos la respuesta de la nube
                    res = supabase.table('ventas').insert(datos).execute()
                    if res.data:
                        # Guardamos el ID real que Supabase le asignó al ticket
                        ultimo_id_venta_nube = res.data[0]['id']
                
                elif tabla == 'ventas_detalle' and ultimo_id_venta_nube:
                    # 2. Si es un detalle, le ponemos el ID del ticket que acabamos de crear
                    datos['venta_id'] = ultimo_id_venta_nube
                    supabase.table('ventas_detalle').insert(datos).execute()
                
                else:
                    # 3. Cualquier otro insert que no sea de ventas (productos, clientes, etc.)
                    supabase.table(tabla).insert(datos).execute()

            elif operacion == 'update':
                supabase.table(tabla).update(datos).eq("empresa_id", user_business_id).eq(p['col_filtro'], p['val_filtro']).execute()
            
            elif operacion == 'delete':
                supabase.table(tabla).delete().eq("empresa_id", user_business_id).eq(p['col_filtro'], p['val_filtro']).execute()

            # Si la operación en la nube fue exitosa, borramos del buzón local
            cur.execute("DELETE FROM buzon_salida WHERE id = ?", (p_id,))
            
        except Exception as e:
            print(f"Error sincronizando {tabla}: {e}")
            errores += 1

    conn.commit()
    conn.close()
    
@app.get("/matar-pendientes")
def matar_pendientes(user_business_id: str = Cookie(None)):
    # Primero forzamos que se suba todo a la nube
    res = sincronizar_buzon(user_business_id)
    
    # Si la sincronización falló, avisamos
    if not res.get("ok", False):
        return {"msg": "Error al subir: " + res.get("msg", "Desconocido")}
        
    return {"msg": "✅ ¡Todo subido a Supabase y buzón limpio!"}

@app.post("/guardar-cotizacion")
def guardar_cotizacion(payload: dict = Body(...), user_business_id: Optional[str] = Cookie(None), user_business_name: Optional[str] = Cookie(None)):
    if not user_business_id: raise HTTPException(401)
    f = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    link_archivo = payload.get('link_archivo', '')
    conn = conectar(user_business_id); cur = conn.cursor()
    cur.execute("INSERT INTO cotizaciones (fecha, cliente, total, link_archivo) VALUES (?, ?, ?, ?)", (f, payload['cliente'], payload['total'], link_archivo))
    c_id = cur.lastrowid
    for i in payload['items']: cur.execute("INSERT INTO cotizaciones_detalle (id_cotizacion, codigo, descripcion, cantidad, precio) VALUES (?, ?, ?, ?, ?)", (c_id, i['cod'], i['desc'], i['cant'], i['pre']))
    conn.commit(); conn.close()
    n_comercial = urllib.parse.unquote(user_business_name).upper() if user_business_name else "MI NEGOCIO"
    msj = f"*{n_comercial} - COTIZACIÓN*\nFolio: #{c_id}\nCliente: {payload['cliente']}\nTotal Estimado: ${payload['total']:.2f}\n(Precios sujetos a cambio)"
    return {"ok": True, "mensaje_whatsapp": msj}

@app.get("/lista-cotizaciones")
def lista_cotizaciones(user_business_id: Optional[str] = Cookie(None)):
    if not user_business_id: raise HTTPException(401)
    conn = conectar(user_business_id); conn.row_factory = sqlite3.Row
    res = conn.execute("SELECT * FROM cotizaciones WHERE estado = 'ACTIVA' ORDER BY id DESC").fetchall(); conn.close(); return [dict(row) for row in res]

@app.get("/detalle-cotizacion/{id_cot}")
def detalle_cotizacion(id_cot: int, user_business_id: Optional[str] = Cookie(None)):
    if not user_business_id: raise HTTPException(401)
    conn = conectar(user_business_id); conn.row_factory = sqlite3.Row
    res = conn.execute("SELECT codigo as cod, descripcion as desc, cantidad as cant, precio as pre FROM cotizaciones_detalle WHERE id_cotizacion = ?", (id_cot,)).fetchall(); conn.close(); return [dict(row) for row in res]

@app.post("/borrar-cotizacion/{id_cot}")
def borrar_cotizacion(id_cot: int, user_business_id: Optional[str] = Cookie(None)):
    if not user_business_id: raise HTTPException(401)
    conn = conectar(user_business_id); conn.execute("UPDATE cotizaciones SET estado = 'BORRADA' WHERE id = ?", (id_cot,)); conn.commit(); conn.close(); return {"ok": True}

@app.get("/pendientes")
def pendientes(user_business_id: Optional[str] = Cookie(None)):
    if not user_business_id: raise HTTPException(401)
    conn = conectar(user_business_id); conn.row_factory = sqlite3.Row
    res = conn.execute("SELECT id, fecha, total, cliente, estado, saldo_pendiente, link_archivo FROM ventas WHERE estado IN ('PENDIENTE', 'CREDITO', 'APARTADO') ORDER BY id DESC").fetchall(); conn.close(); return [dict(row) for row in res]

@app.get("/historial")
def historial(user_business_id: Optional[str] = Cookie(None)):
    if not user_business_id: raise HTTPException(401)
    conn = conectar(user_business_id); conn.row_factory = sqlite3.Row
    res = conn.execute("SELECT id, fecha, total, cliente, estado, saldo_pendiente, link_archivo FROM ventas ORDER BY id DESC LIMIT 50").fetchall(); conn.close(); return [dict(row) for row in res]

@app.get("/detalle-venta/{id_v}")
def detalle_venta(id_v: int, user_business_id: Optional[str] = Cookie(None)):
    if not user_business_id: raise HTTPException(401)
    conn = conectar(user_business_id); conn.row_factory = sqlite3.Row
    res = conn.execute("SELECT descripcion, cantidad, total_cobrado FROM ventas_detalle WHERE id_venta = ?", (id_v,)).fetchall(); conn.close(); return [dict(row) for row in res]

@app.get("/abonos/{id_v}")
def abonos(id_v: int, user_business_id: Optional[str] = Cookie(None)):
    if not user_business_id: raise HTTPException(401)
    conn = conectar(user_business_id); conn.row_factory = sqlite3.Row
    res = conn.execute("SELECT fecha, monto FROM abonos WHERE id_venta = ?", (id_v,)).fetchall(); conn.close(); return [dict(row) for row in res]

@app.post("/liquidar")
def liquidar(bg_tasks: BackgroundTasks, payload: dict = Body(...), user_name: Optional[str] = Cookie(None), user_business_id: Optional[str] = Cookie(None)):
    if not user_business_id: raise HTTPException(401)
    id_v = payload['id']; monto = payload['monto']; f = datetime.now().strftime("%Y-%m-%d %H:%M:%S"); cajero = user_name or "SISTEMA"
    conn = conectar(user_business_id); cur = conn.cursor()
    cur.execute("INSERT INTO abonos (id_venta, fecha, monto, cajero, metodo) VALUES (?, ?, ?, ?, 'EFECTIVO')", (id_v, f, monto, cajero))
    bg_tasks.add_task(sync_to_supabase, "abonos", {"empresa_id": user_business_id, "id_venta": id_v, "fecha": f, "monto": monto, "cajero": cajero, "metodo": 'EFECTIVO'})
    
    cur.execute("SELECT saldo_pendiente FROM ventas WHERE id = ?", (id_v,)); saldo_actual = cur.fetchone()[0]; nuevo_saldo = saldo_actual - monto
    if nuevo_saldo <= 0: 
        cur.execute("UPDATE ventas SET saldo_pendiente = 0, estado = 'COMPLETADA' WHERE id = ?", (id_v,))
        bg_tasks.add_task(sync_update_supabase, "ventas", {"saldo_pendiente": 0, "estado": 'COMPLETADA'}, "id", id_v, user_business_id)
    else: 
        cur.execute("UPDATE ventas SET saldo_pendiente = ? WHERE id = ?", (nuevo_saldo, id_v))
        bg_tasks.add_task(sync_update_supabase, "ventas", {"saldo_pendiente": nuevo_saldo}, "id", id_v, user_business_id)
    conn.commit(); conn.close(); return {"ok": True}

@app.post("/gasto")
def gasto(bg_tasks: BackgroundTasks, payload: dict = Body(...), user_name: Optional[str] = Cookie(None), user_business_id: Optional[str] = Cookie(None)):
    if not user_business_id: raise HTTPException(401)
    f = datetime.now().strftime("%Y-%m-%d %H:%M:%S"); cajero = user_name or "SISTEMA"
    conn = conectar(user_business_id); cur = conn.cursor()
    cur.execute("INSERT INTO gastos (fecha, descripcion, monto, cajero) VALUES (?, ?, ?, ?)", (f, payload['desc'], payload['monto'], cajero))
    g_id = cur.lastrowid
    conn.commit(); conn.close()
    bg_tasks.add_task(sync_to_supabase, "gastos", {"id": g_id, "empresa_id": user_business_id, "fecha": f, "descripcion": payload['desc'], "monto": payload['monto'], "cajero": cajero})
    return {"ok": True}

@app.post("/guardar-config-ticket")
def guardar_config_ticket(payload: dict = Body(...), user_business_id: Optional[str] = Cookie(None)):
    if not user_business_id: raise HTTPException(401)
    conn = conectar(user_business_id)
    for clave, valor in payload.items():
        conn.execute("INSERT OR REPLACE INTO configuracion (parametro, valor) VALUES (?, ?)", (clave, valor))
    conn.commit(); conn.close()
    return {"ok": True}

@app.post("/fotos-masivas")
async def cargar_fotos_masivas(bg_tasks: BackgroundTasks, user_business_id: Optional[str] = Cookie(None)):
    if not user_business_id: raise HTTPException(401)
    
    # Esta carpeta es donde tú pondrás las fotos manualmente antes de darle clic
    CARPETA_ORIGEN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "CargarFotos")
    if not os.path.exists(CARPETA_ORIGEN):
        os.makedirs(CARPETA_ORIGEN)
        return {"ok": False, "msg": f"Carpeta creada. Pon tus fotos en: {CARPETA_ORIGEN}"}

    conn = conectar(user_business_id); cur = conn.cursor()
    archivos = os.listdir(CARPETA_ORIGEN)
    procesados = 0

    for archivo in archivos:
        if archivo.lower().endswith(('.png', '.jpg', '.jpeg')):
            codigo = os.path.splitext(archivo)[0] # Quita el .jpg y deja el código
            ruta_origen = os.path.join(CARPETA_ORIGEN, archivo)
            nombre_final = f"prod_{codigo}{os.path.splitext(archivo)[1]}"
            ruta_destino = os.path.join(FOTOS_DIR, nombre_final)
            
            # Mover archivo y actualizar BD
            shutil.copy2(ruta_origen, ruta_destino)
            cur.execute("UPDATE productos SET imagen = ? WHERE CodigoProducto = ?", (nombre_final, codigo))
            
            # Sincronizar con la nube en segundo plano
            bg_tasks.add_task(sync_foto_supabase, ruta_destino, nombre_final)
            procesados += 1

    conn.commit(); conn.close()
    return {"ok": True, "msg": f"¡Éxito! Se actualizaron {procesados} fotos de productos."}

@app.get("/premium", response_class=HTMLResponse)
def vista_premium():
    html_skin = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>POS . SYS - Premium</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <style>
            :root { --bg-dark: #0d0f12; --bg-panel: #16191f; --accent-yellow: #facc15; --text-main: #f3f4f6; --text-muted: #9ca3af; --border-color: #2b303b; }
            * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Inter', sans-serif; }
            body { background-color: var(--bg-dark); color: var(--text-main); min-height: 100vh; }
            .navbar { background-color: var(--bg-panel); border-bottom: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: center; padding: 0 40px; height: 70px; }
            .logo { font-size: 24px; font-weight: 800; letter-spacing: 2px; color: var(--text-main); }
            .logo span { color: var(--accent-yellow); }
            .nav-links { display: flex; gap: 40px; }
            .nav-links a { color: var(--text-muted); text-decoration: none; font-size: 14px; font-weight: 600; text-transform: uppercase; padding: 24px 0; transition: all 0.3s; border-bottom: 3px solid transparent; }
            .nav-links a:hover { color: var(--text-main); }
            .nav-links a.active { color: var(--accent-yellow); border-bottom: 3px solid var(--accent-yellow); }
            .container { max-width: 1200px; margin: 40px auto; padding: 0 20px; }
            .section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; }
            h1 { font-size: 28px; font-weight: 700; }
            .btn-primary { background-color: var(--accent-yellow); color: #000; border: none; padding: 10px 24px; border-radius: 8px; font-weight: 700; cursor: pointer; display: flex; gap: 8px; }
            .table-container { background-color: var(--bg-panel); border-radius: 12px; border: 1px solid var(--border-color); overflow: hidden; }
            table { width: 100%; border-collapse: collapse; }
            th { text-align: left; padding: 20px; color: var(--text-muted); font-size: 12px; font-weight: 600; text-transform: uppercase; border-bottom: 2px solid var(--accent-yellow); }
            td { padding: 18px 20px; font-size: 15px; border-bottom: 1px solid var(--border-color); }
            .item-code { color: var(--accent-yellow); font-family: monospace; }
        </style>
    </head>
    <body>
        <nav class="navbar">
            <div class="logo">POS <span>.</span> SYS</div>
            <div class="nav-links"><a href="#" class="active">Inventario</a><a href="/">Volver al Sistema Real</a></div>
        </nav>
        <div class="container">
            <div class="section-header">
                <h1>INVENTARIO DE PRUEBA</h1>
                <button class="btn-primary"><i class="fa-solid fa-plus"></i> NUEVO</button>
            </div>
            <div class="table-container">
                <table>
                    <thead><tr><th>Nombre</th><th>Código</th><th>Categoría</th><th>Precio</th></tr></thead>
                    <tbody>
                        <tr><td>Playera Sublimación</td><td class="item-code">SUB-001</td><td>Textil</td><td>$120.00</td></tr>
                        <tr><td>Film DTF Premium</td><td class="item-code">DTF-992</td><td>Consumibles</td><td>$350.00</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    </body>
    </html>

    """
    return html_skin

if __name__ == "__main__":
    puerto = 8000
    try: ngrok.kill()
    except: pass
    print(f"\n🚀 MICROCOM POS PREMIUM - INICIANDO...")
    url_p = None
    try: print(f"🌐 NGROK ONLINE: {ngrok.connect(puerto).public_url}")
    except: pass
    
    # Truco para abrir como App Independiente en Windows
    import subprocess
    url_local = f"http://127.0.0.1:{puerto}"
    try:
        # Intenta abrir con Chrome en modo App
        subprocess.Popen(['start', 'chrome', f'--app={url_local}'], shell=True)
    except:
        try:
            # Si no hay Chrome, intenta con Edge en modo App
            subprocess.Popen(['start', 'msedge', f'--app={url_local}'], shell=True)
        except:
            # Respaldo normal
            import webbrowser; webbrowser.open(url_local)
            
    uvicorn.run(app, host="0.0.0.0", port=puerto)