import os
import io
import base64
import time
import hashlib
from supabase import create_client
import qrcode
import random
import string
import numpy as np
import secrets
from datetime import datetime
from flask import Flask, render_template, request, send_file, redirect
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageEnhance
import fitz  # PyMuPDF
from qreader import QReader

# --- CONFIGURACIÓN DE SUPABASE ---
SUPABASE_URL = "https://xyjycsnxbcutwwelrogz.supabase.co"
SUPABASE_KEY = "sb_secret_3bq1DNAwQdU3yNN8_-iHCw_jMchEnqX" 
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

app = Flask(__name__)
# Este es el dominio que verán los clientes en el QR
DOMINIO_PUBLICO = "https://publicidad-certificada.sunarpgobpe.site"
ultimo_recorte_qr = None
peticiones_en_vuelo = {}

# --- CONFIGURACIÓN DE RUTAS ---
FOLDER_FUENTES = "fuentes"
FOLDER_IMAGENES = "imagenes"
FONDO_TIVE1 = os.path.join("static", "tive.png")
FONDO_TIVE2 = os.path.join("static", "tive2.png")
FONDO_TIVE3 = os.path.join("static", "tive3.png")

FUENTE_GENERAL = os.path.join(FOLDER_FUENTES, "phagspa.ttf")
FUENTE_ARIAL = os.path.join(FOLDER_FUENTES, "arial.ttf")
FUENTE_ARIALBD = os.path.join(FOLDER_FUENTES, "arialbd.ttf")
FUENTE_ROBOTOBD = os.path.join(FOLDER_FUENTES, "robotobd.ttf")

COLOR_GRIS_73 = (130, 130, 130)  
COLOR_NEGRO = (0, 0, 0)
COLOR_GRISCLARO = (203, 203, 203)
COORD_FOTO = (1159, 2245) 
COORD_PEGADO_PDF = (230, 200)

CONFIG_CAMPOS = {
    "verificacion": (845, 288, 30, None, COLOR_NEGRO), 
    "n_titulo": (670, 331, 30, None, COLOR_NEGRO),
    "fecha": (638, 374, 30, None, COLOR_NEGRO),
    "zona_registral": (187, 689, 34, FUENTE_ARIALBD, COLOR_GRIS_73),
    "sede": (185, 735, 34, FUENTE_ARIALBD, COLOR_GRIS_73),
    "partida": (501, 840, 30, None, COLOR_NEGRO), 
    "dua": (375, 903, 30, None, COLOR_NEGRO),
    "titulo": (321, 966, 30, None, COLOR_NEGRO),
    "fecha_titulo": (485, 1029, 30, None, COLOR_NEGRO),
    "categoria": (383, 1477, 30, None, COLOR_NEGRO),
    "marca": (326, 1527, 30, None, COLOR_NEGRO),
    "modelo": (338, 1576, 30, None, COLOR_NEGRO),
    "color": (311, 1626, 30, None, COLOR_NEGRO),
    "vin": (469, 1676, 30, None, COLOR_NEGRO),
    "serie": (494, 1729, 30, None, COLOR_NEGRO),
    "motor": (499, 1777, 30, None, COLOR_NEGRO),
    "carroceria": (399, 1827, 30, None, COLOR_NEGRO),
    "potencia": (362, 1877, 30, None, COLOR_NEGRO),
    "form_rod": (397, 1927, 30, None, COLOR_NEGRO),
    "combustible": (425, 1975, 30, None, COLOR_NEGRO),
    "asientos": (390, 2039, 30, None, COLOR_NEGRO),
    "pasajeros": (390, 2088, 30, None, COLOR_NEGRO),
    "ruedas": (390, 2141, 30, None, COLOR_NEGRO),
    "ejes": (390, 2189, 30, None, COLOR_NEGRO),
    "cilindros": (751, 2039, 30, None, COLOR_NEGRO),
    "longitud": (751, 2088, 30, None, COLOR_NEGRO),
    "altura": (751, 2141, 30, None, COLOR_NEGRO),
    "ancho": (751, 2189, 30, None, COLOR_NEGRO),
    "cilindrada": (1242, 2039, 30, None, COLOR_NEGRO),
    "p_bruto": (1242, 2088, 30, None, COLOR_NEGRO),
    "p_neto": (1242, 2141, 30, None, COLOR_NEGRO),
    "carga_util": (1242, 2189, 30, None, COLOR_NEGRO),
    "año_modelo": (1413, 1527, 30, None, COLOR_NEGRO),
    "año_fabricacion": (1413, 1476, 30, None, COLOR_NEGRO),
    "version": (1028, 1927, 30, None, COLOR_NEGRO),
    "numero_tarjeta":(1393, 1396, 30, FUENTE_ARIAL, COLOR_GRISCLARO),
    "placa":(1136, 947, 81, FUENTE_ROBOTOBD, COLOR_NEGRO),
    "placa_anterior": (1235, 1150, 30, None, COLOR_NEGRO)   
}

def generar_imagen_pil(texto_input, modo_azura=False):
    lineas = texto_input.split('\n')
    datos_dict = {}
    
    for l in lineas:
        if ":" in l:
            p = l.split(':', 1)
            datos_dict[p[0].strip().lower()] = p[1].strip()

    # --- AUTO-GENERACIÓN DE VARIABLES SI ESTÁN VACÍAS ---
    if not datos_dict.get("verificacion"):
        datos_dict["verificacion"] = ''.join(random.choices(string.digits, k=8))
    
    if not datos_dict.get("numero_tarjeta"):
        datos_dict["numero_tarjeta"] = f"10{random.randint(10000000, 99999999)}"
        
    if not datos_dict.get("fecha"):
        datos_dict["fecha"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        
    if not datos_dict.get("n_titulo"):
        datos_dict["n_titulo"] = str(random.randint(10000000, 99999999))

    # Selección de fondo
    tiene_placa_ant = bool(datos_dict.get("placa_anterior"))
    tiene_año_fab = bool(datos_dict.get("año_fabricacion"))

    if modo_azura: ruta_fondo = FONDO_TIVE1
    elif tiene_placa_ant: ruta_fondo = FONDO_TIVE3
    elif tiene_año_fab: ruta_fondo = FONDO_TIVE2
    else: ruta_fondo = FONDO_TIVE1

    if not os.path.exists(ruta_fondo): return None

    img = Image.open(ruta_fondo).convert("RGB")
    draw = ImageDraw.Draw(img)

    # Pegado de foto aleatoria por sede
    if datos_dict.get("foto"):
        ruta_carpeta = os.path.join(FOLDER_IMAGENES, datos_dict["foto"]) 
        if os.path.exists(ruta_carpeta) and os.path.isdir(ruta_carpeta):
            archivos = [f for f in os.listdir(ruta_carpeta) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
            if archivos:
                foto_img = Image.open(os.path.join(ruta_carpeta, random.choice(archivos))).convert("RGBA")
                img.paste(foto_img, COORD_FOTO, foto_img)

    # Dibujar campos
    for etiqueta, valor_raw in datos_dict.items():
        if etiqueta in CONFIG_CAMPOS and valor_raw:
            valor = valor_raw if any(u in valor_raw.lower() for u in ['tn', 'mt']) else valor_raw.upper()
            x, y, tam, f_esp, col = CONFIG_CAMPOS[etiqueta]
            ruta_f = f_esp if f_esp else FUENTE_GENERAL
            try:
                fuente = ImageFont.truetype(ruta_f, tam)
                draw.text((x, y), valor, font=fuente, fill=col, anchor="lt")
            except:
                fuente = ImageFont.truetype(FUENTE_GENERAL, tam)
                draw.text((x, y), valor, font=fuente, fill=col, anchor="lt")
    return img

def extraer_recorte_pdf(pdf_stream):
    try:
        doc = fitz.open(stream=pdf_stream, filetype="pdf")
        pagina = doc[0]
        qreader = QReader(model_size='m')
        pix_busqueda = pagina.get_pixmap(matrix=fitz.Matrix(4, 4))
        img_busqueda = Image.frombytes("RGB", [pix_busqueda.width, pix_busqueda.height], pix_busqueda.samples)
        img_pre = ImageOps.grayscale(img_busqueda)
        img_pre = ImageEnhance.Contrast(img_pre).enhance(2.0)
        detecciones = qreader.detect_and_decode(image=np.array(img_pre.convert("RGB")), return_detections=True)
        
        if detecciones and len(detecciones) > 0:
            det = detecciones[0]
            bbox = det.get('bbox_xyxy') if isinstance(det, dict) else getattr(det, 'bbox_xyxy', None)
            if bbox is not None:
                padding = 12
                rect_final = fitz.Rect((bbox[0]/4)-padding, (bbox[1]/4)-padding, (bbox[2]/4)+padding, (bbox[3]/4)+padding)
            else: rect_final = fitz.Rect(45, 40, 120, 115) 
        else: rect_final = fitz.Rect(45, 40, 120, 115)

        zoom_final = 4.29
        pix_recorte = pagina.get_pixmap(clip=rect_final, matrix=fitz.Matrix(zoom_final, zoom_final))
        img_recorte = Image.frombytes("RGB", [pix_recorte.width, pix_recorte.height], pix_recorte.samples)
        doc.close()
        return img_recorte
    except: return None

@app.route('/', methods=['GET', 'POST'])
def index():
    # Si alguien entra desde el dominio público, lo mandamos a la web informativa
    if "sunarpgobpe.site" in request.host:
        return redirect("https://www.gob.pe/sunarp", code=301)

    global ultimo_recorte_qr
    imagen_base64, texto_previo, depto_previo, pos_guion = None, "", "", "cen"
    if request.method == 'POST':
        texto_previo = request.form.get('texto_datos', '')
        depto_previo = request.form.get('depto_nombre', '')
        pos_guion = request.form.get('pos_guion', 'cen')
        img = generar_imagen_pil(texto_previo)
        if img:
            url_temp = f"https://publicidad-certificada.sunarpgobpe.site/ver/{secrets.token_hex(4)}"
            qr = qrcode.QRCode(version=5, box_size=10, border=1)
            qr.add_data(url_temp); qr.make(fit=True)
            qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGBA").resize((250, 250), Image.Resampling.LANCZOS)
            img.paste(qr_img, COORD_PEGADO_PDF)
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG", quality=90)
            imagen_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
    return render_template('index.html', imagen_preview=imagen_base64, texto=texto_previo, depto_previo=depto_previo, pos_guion=pos_guion)

@app.route('/descargar', methods=['POST'])
def descargar():
    global peticiones_en_vuelo
    texto = request.form.get('texto_datos', '')
    huella = hashlib.md5(texto.encode()).hexdigest()
    ahora = time.time()
    if huella in peticiones_en_vuelo and ahora - peticiones_en_vuelo[huella] < 7: return "", 204
    peticiones_en_vuelo[huella] = ahora

    img = generar_imagen_pil(texto)
    if img:
        id_final = secrets.token_hex(16).upper()
        # Usamos la constante definida arriba
        url_final = f"{DOMINIO_PUBLICO}/servicio/verCertificado/{id_final}"
        qr = qrcode.QRCode(version=5, box_size=10, border=1)
        qr.add_data(url_final); qr.make(fit=True)
        qr_def = qr.make_image(fill_color="black", back_color="white").convert("RGBA").resize((250, 250), Image.Resampling.LANCZOS)
        img.paste(qr_def, COORD_PEGADO_PDF)

        pdf_io = io.BytesIO()
        img.convert("RGB").save(pdf_io, 'PDF', resolution=300.0)
        pdf_bytes = pdf_io.getvalue()
        pdf_io.seek(0)
        
        try:
            supabase.storage.from_('reportes').upload(path=f"TIVE_{id_final}.pdf", file=pdf_bytes, file_options={"content-type": "application/pdf"})
        except: pass

        placa = "S-P"
        for l in texto.split('\n'):
            if l.lower().startswith('placa:'): placa = l.split(':')[1].strip().upper(); break

        return send_file(pdf_io, mimetype='application/pdf', as_attachment=True, download_name=f'TIVE_{placa}.pdf')
    return "Error", 500

@app.route('/servicio/verCertificado/<id_final>')
def ver_certificado(id_final):
    try:
        res = supabase.storage.from_('reportes').get_public_url(f"TIVE_{id_final}.pdf")
        return redirect(res, code=302)
    except: 
        # En lugar de error 404, enviamos al usuario a tu página principal
        return redirect("https://www.gob.pe/sunarp", code=302)

if __name__ == '__main__':
    app.run(debug=True)