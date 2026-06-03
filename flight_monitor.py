"""
Monitoreo de tiquetes BAQ → BOG y BOG → BAQ
Usa SerpAPI (Google Flights) — cobertura completa de aerolíneas en Colombia.
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

# Credenciales (variables de entorno / GitHub Secrets)
GMAIL_USER     = os.environ["GMAIL_USER"]
GMAIL_PASSWORD = os.environ["GMAIL_PASSWORD"]
NOTIFY_EMAIL   = os.environ["NOTIFY_EMAIL"]
SERPAPI_KEY    = os.environ["SERPAPI_KEY"]

SERPAPI_URL = "https://serpapi.com/search.json"
# ───────────────────────────────────────────────────────────────────────────────


def buscar_precio(origin: str, destination: str, date: str) -> dict | None:
    """Consulta Google Flights vía SerpAPI."""
    params = {
        "engine":           "google_flights",
        "departure_id":     origin,
        "arrival_id":       destination,
        "outbound_date":    date,
        "type":             "2",          # 2 = one-way (consultamos cada trayecto por separado)
        "currency":         "COP",
        "hl":               "es",
        "gl":               "co",
        "api_key":          SERPAPI_KEY,
    }
    try:
        resp = requests.get(SERPAPI_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        # Google Flights devuelve "best_flights" (recomendados) y "other_flights"
        vuelos = data.get("best_flights") or data.get("other_flights") or []
        if not vuelos:
            print(f"    Sin vuelos en respuesta para {origin}→{destination} {date}")
            return None

        # El primero es el más barato (Google ya los ordena)
        mejor = min(vuelos, key=lambda v: v.get("price", 9_999_999))
        segmento = mejor.get("flights", [{}])[0]

        return {
            "precio":    mejor.get("price", 0),
            "aerolinea": segmento.get("airline", "N/A"),
            "numero":    segmento.get("flight_number", "N/A"),
            "salida":    segmento.get("departure_airport", {}).get("time", "N/A"),
            "duracion":  mejor.get("total_duration", 0),
        }
    except Exception as e:
        print(f"[ERROR] {origin}→{destination} {date}: {e}")
        return None


def formatear_cop(valor: int) -> str:
    return f"${valor:,.0f} COP"


def enviar_correo(asunto: str, cuerpo_html: str):
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
            <td style="padding:10px;border-bottom:1px solid #e5e7eb">{r['duracion']} min</td>
            <td style="padding:10px;border-bottom:1px solid #e5e7eb">{badge}</td>
        </tr>"""

    return f"""
    <html><body style="font-family:Arial,sans-serif;max-width:680px;margin:0 auto">
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
              <th style="padding:10px;text-align:left">Duración</th>
              <th style="padding:10px;text-align:left">Estado</th>
            </tr>
          </thead>
          <tbody>{filas}</tbody>
        </table>
        <p style="color:#6b7280;font-size:12px;margin-top:16px">
          Datos vía Google Flights · Enviado automáticamente por GitHub Actions.
        </p>
      </div>
    </body></html>
    """


def main():
    print(f"[{datetime.now()}] Iniciando búsqueda de vuelos...")

    resultados = []
    hay_alerta = False

    # ── IDA ──
    ida = buscar_precio(ORIGIN_IDA, DESTINATION_IDA, DATE_IDA)
    if ida:
        alerta = ida["precio"] <= PRECIO_MAXIMO_COP
        hay_alerta = hay_alerta or alerta
        resultados.append({
            "ruta":      f"{ORIGIN_IDA} → {DESTINATION_IDA}",
            "fecha":     DATE_IDA,
            "precio":    ida["precio"],
            "aerolinea": ida["aerolinea"],
            "duracion":  ida["duracion"],
            "alerta":    alerta,
        })
        print(f"  IDA:    {formatear_cop(ida['precio'])} ({ida['aerolinea']}) — {'¡ALERTA!' if alerta else 'sin alerta'}")
    else:
        print("  IDA:    sin resultados.")

    # ── VUELTA ──
    vuelta = buscar_precio(ORIGIN_VUELTA, DESTINATION_VUELTA, DATE_VUELTA)
    if vuelta:
        alerta = vuelta["precio"] <= PRECIO_MAXIMO_COP
        hay_alerta = hay_alerta or alerta
        resultados.append({
            "ruta":      f"{ORIGIN_VUELTA} → {DESTINATION_VUELTA}",
            "fecha":     DATE_VUELTA,
            "precio":    vuelta["precio"],
            "aerolinea": vuelta["aerolinea"],
            "duracion":  vuelta["duracion"],
            "alerta":    alerta,
        })
        print(f"  VUELTA: {formatear_cop(vuelta['precio'])} ({vuelta['aerolinea']}) — {'¡ALERTA!' if alerta else 'sin alerta'}")
    else:
        print("  VUELTA: sin resultados.")

    if not resultados:
        print("No hay resultados para enviar.")
        return

    asunto = (
        "✅ ¡Tiquete BAQ↔BOG bajo tu límite!" if hay_alerta
        else f"✈️ Monitor vuelos BAQ↔BOG — {datetime.now().strftime('%d/%m/%Y')}"
    )
    enviar_correo(asunto, construir_html(resultados))


if __name__ == "__main__":
    main()
