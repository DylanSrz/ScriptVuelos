"""
Monitoreo de tiquetes BAQ → BOG y BOG → BAQ
Usa SerpAPI (Google Flights). Lista TODOS los vuelos por debajo del umbral.
Incluye link directo a Google Flights para reservar.
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

PRECIO_MAXIMO_COP = 200_000          # Solo se notifican vuelos <= este valor

GMAIL_USER     = os.environ["GMAIL_USER"]
GMAIL_PASSWORD = os.environ["GMAIL_PASSWORD"]
NOTIFY_EMAIL   = os.environ["NOTIFY_EMAIL"]
SERPAPI_KEY    = os.environ["SERPAPI_KEY"]

SERPAPI_URL = "https://serpapi.com/search.json"
# ───────────────────────────────────────────────────────────────────────────────


def google_flights_link(origin: str, destination: str, date: str) -> str:
    """Genera un link directo de búsqueda en Google Flights."""
    return (
        f"https://www.google.com/travel/flights"
        f"?q=Flights%20from%20{origin}%20to%20{destination}%20on%20{date}"
        f"&curr=COP&hl=es"
    )


def buscar_vuelos(origin: str, destination: str, date: str) -> list[dict]:
    """Devuelve TODOS los vuelos disponibles para la ruta y fecha."""
    params = {
        "engine":        "google_flights",
        "departure_id":  origin,
        "arrival_id":    destination,
        "outbound_date": date,
        "type":          "2",          # one-way
        "currency":      "COP",
        "hl":            "es",
        "gl":            "co",
        "api_key":       SERPAPI_KEY,
    }
    try:
        resp = requests.get(SERPAPI_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        # Combinar "best_flights" (recomendados) y "other_flights" (los demás)
        todos = (data.get("best_flights") or []) + (data.get("other_flights") or [])

        vuelos_parseados = []
        for v in todos:
            segmento = (v.get("flights") or [{}])[0]
            vuelos_parseados.append({
                "precio":     v.get("price", 0),
                "aerolinea":  segmento.get("airline", "N/A"),
                "numero":     segmento.get("flight_number", "N/A"),
                "hora_salida":segmento.get("departure_airport", {}).get("time", "N/A"),
                "hora_llegada": segmento.get("arrival_airport", {}).get("time", "N/A"),
                "duracion":   v.get("total_duration", 0),
            })

        # Eliminar duplicados (mismo vuelo puede aparecer en best y en other)
        vistos = set()
        unicos = []
        for v in vuelos_parseados:
            clave = (v["aerolinea"], v["numero"], v["hora_salida"], v["precio"])
            if clave not in vistos:
                vistos.add(clave)
                unicos.append(v)

        # Ordenar por precio ascendente
        return sorted(unicos, key=lambda x: x["precio"])

    except Exception as e:
        print(f"[ERROR] {origin}→{destination} {date}: {e}")
        return []


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


def construir_seccion_ruta(titulo: str, fecha: str, link: str,
                            vuelos_bajo_umbral: list[dict],
                            precio_minimo_total: int | None) -> str:
    """Construye el bloque HTML para una ruta."""
    if not vuelos_bajo_umbral:
        # Mostrar el precio mínimo aunque no cumpla
        info_extra = (
            f"<p style='color:#dc2626;margin:8px 0 0'>"
            f"Sin vuelos bajo ${PRECIO_MAXIMO_COP:,.0f} COP. "
            f"Precio más bajo encontrado: <strong>{formatear_cop(precio_minimo_total) if precio_minimo_total else 'N/A'}</strong>"
            f"</p>"
        )
        return f"""
        <div style="background:white;border-radius:8px;padding:16px;margin-bottom:16px;border-left:4px solid #dc2626">
            <h3 style="margin:0 0 4px;color:#1e40af">{titulo}</h3>
            <p style="margin:0;color:#6b7280">Fecha: {fecha}</p>
            {info_extra}
            <p style="margin:12px 0 0"><a href="{link}" style="background:#1e40af;color:white;padding:8px 14px;border-radius:6px;text-decoration:none;font-size:14px">🔍 Ver en Google Flights</a></p>
        </div>
        """

    filas = ""
    for v in vuelos_bajo_umbral:
        filas += f"""
        <tr>
            <td style="padding:8px;border-bottom:1px solid #e5e7eb;font-weight:bold;color:#16a34a">{formatear_cop(v['precio'])}</td>
            <td style="padding:8px;border-bottom:1px solid #e5e7eb">{v['aerolinea']} {v['numero']}</td>
            <td style="padding:8px;border-bottom:1px solid #e5e7eb">{v['hora_salida']} → {v['hora_llegada']}</td>
            <td style="padding:8px;border-bottom:1px solid #e5e7eb">{v['duracion']} min</td>
        </tr>"""

    return f"""
    <div style="background:white;border-radius:8px;padding:16px;margin-bottom:16px;border-left:4px solid #16a34a">
        <h3 style="margin:0 0 4px;color:#1e40af">{titulo}</h3>
        <p style="margin:0 0 12px;color:#6b7280">Fecha: {fecha} · <strong style="color:#16a34a">{len(vuelos_bajo_umbral)} vuelo(s) bajo ${PRECIO_MAXIMO_COP:,.0f} COP</strong></p>
        <table style="width:100%;border-collapse:collapse;font-size:14px">
            <thead style="background:#f0fdf4">
                <tr>
                    <th style="padding:8px;text-align:left">Precio</th>
                    <th style="padding:8px;text-align:left">Vuelo</th>
                    <th style="padding:8px;text-align:left">Horario</th>
                    <th style="padding:8px;text-align:left">Duración</th>
                </tr>
            </thead>
            <tbody>{filas}</tbody>
        </table>
        <p style="margin:12px 0 0"><a href="{link}" style="background:#16a34a;color:white;padding:8px 14px;border-radius:6px;text-decoration:none;font-size:14px">🎟️ Reservar en Google Flights</a></p>
    </div>
    """


def construir_html(secciones_html: list[str]) -> str:
    return f"""
    <html><body style="font-family:Arial,sans-serif;max-width:720px;margin:0 auto;background:#f9fafb;padding:20px">
      <div style="background:#1e40af;color:white;padding:20px;border-radius:8px 8px 0 0">
        <h2 style="margin:0">✈️ Monitor de Tiquetes BAQ ↔ BOG</h2>
        <p style="margin:4px 0 0;opacity:.85">Revisión del {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
      </div>
      <div style="padding:20px;background:white;border-radius:0 0 8px 8px">
        <p style="margin:0 0 16px">Umbral configurado: <strong>{formatear_cop(PRECIO_MAXIMO_COP)}</strong> por trayecto.</p>
        {''.join(secciones_html)}
        <p style="color:#9ca3af;font-size:12px;margin-top:20px;text-align:center">
          Datos vía Google Flights · Enviado automáticamente por GitHub Actions
        </p>
      </div>
    </body></html>
    """


def main():
    print(f"[{datetime.now()}] Iniciando búsqueda de vuelos...")

    hay_alerta = False
    secciones = []

    rutas = [
        ("✈️ IDA",    ORIGIN_IDA,    DESTINATION_IDA,    DATE_IDA),
        ("🔄 VUELTA", ORIGIN_VUELTA, DESTINATION_VUELTA, DATE_VUELTA),
    ]

    for titulo, origin, destination, date in rutas:
        print(f"\n  Buscando {origin}→{destination} ({date})...")
        todos = buscar_vuelos(origin, destination, date)
        bajo_umbral = [v for v in todos if v["precio"] <= PRECIO_MAXIMO_COP]
        precio_min = todos[0]["precio"] if todos else None

        if bajo_umbral:
            hay_alerta = True
            print(f"    ✅ {len(bajo_umbral)} vuelo(s) bajo {formatear_cop(PRECIO_MAXIMO_COP)}:")
            for v in bajo_umbral:
                print(f"       - {formatear_cop(v['precio'])} | {v['aerolinea']} | {v['hora_salida']}")
        else:
            print(f"    ⏳ Sin vuelos bajo umbral. Mín: {formatear_cop(precio_min) if precio_min else 'N/A'}")

        link = google_flights_link(origin, destination, date)
        secciones.append(construir_seccion_ruta(
            titulo=f"{titulo}: {origin} → {destination}",
            fecha=date,
            link=link,
            vuelos_bajo_umbral=bajo_umbral,
            precio_minimo_total=precio_min,
        ))

    asunto = (
        f"✅ ¡Hay tiquetes BAQ↔BOG bajo {formatear_cop(PRECIO_MAXIMO_COP)}!" if hay_alerta
        else f"✈️ Monitor vuelos BAQ↔BOG — {datetime.now().strftime('%d/%m/%Y')}"
    )
    enviar_correo(asunto, construir_html(secciones))


if __name__ == "__main__":
    main()
