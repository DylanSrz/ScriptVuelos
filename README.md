# ✈️ Monitor de Tiquetes BAQ ↔ BOG

Automatización que corre **todos los días a las 7 AM** (hora Colombia) usando GitHub Actions y te notifica por Gmail cuando encuentra precios por debajo de tu límite.

---

## 📁 Estructura del proyecto

```
tu-repo/
├── flight_monitor.py
└── .github/
    └── workflows/
        └── flight_monitor.yml
```

---

## 🚀 Configuración paso a paso

### 1. Obtener token gratuito de Aviasales

1. Regístrate en https://www.travelpayouts.com
2. Ve a **Herramientas → API** y copia tu **Token**
3. Guárdalo, lo necesitarás en el paso 3

### 2. Crear contraseña de aplicación en Gmail

> Gmail no permite usar tu contraseña normal en scripts. Necesitas una "App Password".

1. Ve a https://myaccount.google.com/security
2. Activa **Verificación en dos pasos** (si no la tienes)
3. Ve a **Contraseñas de aplicaciones**
4. Crea una nueva → elige "Correo" y "Windows" → copia los 16 caracteres

### 3. Agregar los Secrets en GitHub

En tu repositorio de GitHub ve a:
**Settings → Secrets and variables → Actions → New repository secret**

Agrega estos 4 secrets:

| Nombre | Valor |
|--------|-------|
| `GMAIL_USER` | tu correo Gmail (ej: `tunombre@gmail.com`) |
| `GMAIL_PASSWORD` | los 16 caracteres del paso anterior |
| `NOTIFY_EMAIL` | correo donde quieres recibir alertas |
| `AVIASALES_TOKEN` | token de Travelpayouts del paso 1 |

### 4. Subir los archivos al repositorio

```bash
git init
git add .
git commit -m "feat: monitor de vuelos BAQ-BOG"
git remote add origin https://github.com/TU_USUARIO/TU_REPO.git
git push -u origin main
```

### 5. Activar GitHub Actions

1. Ve a la pestaña **Actions** en tu repositorio
2. Si te pide activarlos, acepta
3. Para probar de inmediato: **Actions → Monitor Tiquetes → Run workflow**

---

## 📧 Ejemplo de correo que recibirás

El correo llega con:
- Precio más barato encontrado para cada trayecto
- Aerolínea que lo opera
- Indicador visual si está por debajo de $200.000 COP

Si **hay alerta**, el asunto será:
> ✅ ¡Tiquete BAQ↔BOG bajo tu límite!

Si no hay alerta, igual llega el reporte diario:
> ✈️ Monitor vuelos BAQ↔BOG — 03/06/2026

---

## ⚙️ Personalización

En `flight_monitor.py` puedes cambiar fácilmente:

```python
PRECIO_MAXIMO_COP = 200_000   # Cambia el umbral
DATE_IDA          = "2026-06-23"
DATE_VUELTA       = "2026-06-26"
```

Para que **solo notifique cuando hay precio bajo** (sin reporte diario), busca esta línea en `main()`:

```python
# Siempre notifica (para ver el estado diario).
# Si solo quieres correo cuando hay precio bajo, cambia la condición a: if hay_alerta
```

Y cambia la condición según el comentario.

---

## 🕐 Horario del cron

El workflow corre a las **12:00 UTC = 7:00 AM hora Colombia (UTC-5)**.

Para cambiar el horario, edita la línea en el workflow:
```yaml
- cron: "0 12 * * *"
```
Usa https://crontab.guru para construir el cron que necesites.
