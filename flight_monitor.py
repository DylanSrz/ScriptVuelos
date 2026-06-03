"""
Monitoreo de tiquetes BAQ → BOG y BOG → BAQ
Usa la API de Aviasales (gratuita) para consultar precios.
Notifica por Gmail si el precio está por debajo del umbral definido.
"""

import os
import smtplib
import requests
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ─── CONFIGURACIÓN ─────────────────────────────────────────────────────────────
ORIGIN_IDA      = "BAQ"
DESTINATION_IDA = "BOG"
DATE_IDA        = "2026-06-23"

ORIGIN_VUELTA      = "BOG"
DESTINATION_VUELTA = "BAQ"
DATE_VUELTA        = "2026-06-26"

PRECIO_MAXIMO_COP = 200_000          # Umbral por trayecto
CURRENCY          = "COP"

# Credenciales Gmail (se leen desde variables de entorno / GitHub Secrets)
GMAIL_USER     = os.environ["GMAIL_USER"]       # tu correo @gmail.com
GMAIL_PASSWORD = os.environ["GMAIL_PASSWORD"]   # contraseña de aplicación
NOTIFY_EMAIL   = os.environ["NOTIFY_EMAIL"]     # a quién enviar (puede ser el mismo)

# API Aviasales (token gratuito)
AVIASALES_TOKEN = os.environ["AVIASALES_TOKEN"]
AVIASALES_URL   = "https://api.travelpayouts.com/v1/prices/cheap"
# ───────────────────────────────────────────────────────────────────────────────


def buscar_precio(origin: str, destination: str, date: str) -> dict | None:
    """Consulta el precio más barato para una ruta y fecha dada."""
    params = {
        "origin":       origin,
        "destination":  destination,
        "depart_date":  date,         # formato YYYY-MM-DD
        "currency":     CURRENCY,
        "token":        AVIASALES_TOKEN,
        "limit":        1,
    }
    try:
        resp = requests.get(AVIASALES_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json().get("data", {})

        # La respuesta tiene la forma: {"data": {"BOG": {"0": {price, airline, ...}}}}
        if not data:
            return None

        dest_data = data.get(destination, {})
        if not dest_data:
            return None

        # Tomar el vuelo más barato
        vuelo = list(dest_data.values())[0]
        return {
            "precio":    vuelo.get("price", 0),
            "aerolinea": vuelo.get("airline", "N/A"),
            "numero":    vuelo.get("flight_number", "N/A"),
            "salida":    vuelo.get("departure_at", "N/A"),
        }
    except Exception as e:
        print(f"[ERROR] Al consultar {origin}→{destination} {date}: {e}")
        return None


def formatear_cop(valor: int) -> str:
    return f"${valor:,.0f} COP"


def enviar_correo(asunto: str, cuerpo_html: str):
    """Envía un correo usando Gmail SMTP."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = asunto
    msg["From"]    = GMAIL_USER
    msg["To"]      = NOTIFY_EMAIL
    msg.attach(MIMEText(cuerpo_html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_PASSWORD)
        server.sendmail(GMAIL_USER, NOTIFY_EMAIL, msg.as_string())
    print("[OK] Correo enviado.")


def construir_html(resultados: list[dict]) -> str:
    filas = ""
    for r in resultados:
        color = "#16a34a" if r["alerta"] else "#374151"
        badge = "✅ ¡DEBAJO DEL LÍMITE!" if r["alerta"] else "⏳ Por encima del límite"
        filas += f"""
        <tr>
            <td style="padding:10px;border-bottom:1px solid #e5e7eb">{r['ruta']}</td>
            <td style="padding:10px;border-bottom:1px solid #e5e7eb">{r['fecha']}</td>
            <td style="padding:10px;border-bottom:1px solid #e5e7eb;font-weight:bold;color:{color}">{formatear_cop(r['precio'])}</td>
            <td style="padding:10px;border-bottom:1px solid #e5e7eb">{r['aerolinea']}</td>
            <td style="padding:10px;border-bottom:1px solid #e5e7eb">{badge}</td>
        </tr>"""

    return f"""
    <html><body style="font-family:Arial,sans-serif;max-width:620px;margin:0 auto">
      <div style="background:#1e40af;color:white;padding:20px;border-radius:8px 8px 0 0">
        <h2 style="margin:0">✈️ Monitor de Tiquetes BAQ ↔ BOG</h2>
        <p style="margin:4px 0 0;opacity:.8">Revisión del {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
      </div>
      <div style="padding:20px;background:#f9fafb;border-radius:0 0 8px 8px">
        <p>Umbral máximo configurado: <strong>{formatear_cop(PRECIO_MAXIMO_COP)}</strong> por trayecto.</p>
        <table style="width:100%;border-collapse:collapse;background:white;border-radius:6px;overflow:hidden">
          <thead style="background:#e0e7ff">
            <tr>
              <th style="padding:10px;text-align:left">Ruta</th>
              <th style="padding:10px;text-align:left">Fecha</th>
              <th style="padding:10px;text-align:left">Precio</th>
              <th style="padding:10px;text-align:left">Aerolínea</th>
              <th style="padding:10px;text-align:left">Estado</th>
            </tr>
          </thead>
          <tbody>{filas}</tbody>
        </table>
        <p style="color:#6b7280;font-size:12px;margin-top:16px">
          Este correo fue enviado automáticamente por tu monitor de vuelos en GitHub Actions.
        </p>
      </div>
    </body></html>
    """


def main():
    print(f"[{datetime.now()}] Iniciando búsqueda de vuelos...")

    resultados = []
    hay_alerta = False

    # ── Vuelo de ida ──
    ida = buscar_precio(ORIGIN_IDA, DESTINATION_IDA, DATE_IDA)
    if ida:
        alerta = ida["precio"] <= PRECIO_MAXIMO_COP
        if alerta:
            hay_alerta = True
        resultados.append({
            "ruta":      f"{ORIGIN_IDA} → {DESTINATION_IDA}",
            "fecha":     DATE_IDA,
            "precio":    ida["precio"],
            "aerolinea": ida["aerolinea"],
            "alerta":    alerta,
        })
        print(f"  IDA:    {formatear_cop(ida['precio'])} — {'¡ALERTA!' if alerta else 'sin alerta'}")
    else:
        print("  IDA:    no se encontraron resultados.")

    # ── Vuelo de regreso ──
    vuelta = buscar_precio(ORIGIN_VUELTA, DESTINATION_VUELTA, DATE_VUELTA)
    if vuelta:
        alerta = vuelta["precio"] <= PRECIO_MAXIMO_COP
        if alerta:
            hay_alerta = True
        resultados.append({
            "ruta":      f"{ORIGIN_VUELTA} → {DESTINATION_VUELTA}",
            "fecha":     DATE_VUELTA,
            "precio":    vuelta["precio"],
            "aerolinea": vuelta["aerolinea"],
            "alerta":    alerta,
        })
        print(f"  VUELTA: {formatear_cop(vuelta['precio'])} — {'¡ALERTA!' if alerta else 'sin alerta'}")
    else:
        print("  VUELTA: no se encontraron resultados.")

    if not resultados:
        print("No hay resultados para enviar. Saliendo.")
        return

    # ── Enviar correo ──
    # Siempre notifica (para ver el estado diario).
    # Si solo quieres correo cuando hay precio bajo, cambia la condición a: if hay_alerta
    asunto = (
        "✅ ¡Tiquete BAQ↔BOG bajo tu límite!" if hay_alerta
        else f"✈️ Monitor vuelos BAQ↔BOG — {datetime.now().strftime('%d/%m/%Y')}"
    )
    html = construir_html(resultados)
    enviar_correo(asunto, html)


if __name__ == "__main__":
    main()
