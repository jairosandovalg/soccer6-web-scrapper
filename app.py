import streamlit as st
import pandas as pd
import time
import requests

# Configuración de la interfaz de Streamlit
st.set_page_config(page_title="Bot de Estadísticas Final", layout="wide")
st.title("📊 Monitor de Estadísticas en Vivo - Flashscore & Telegram")
st.subheader("Análisis de métricas en tiempo real con alertas automatizadas y cuotas de Betano")

# Encabezados para simular una petición de navegador común y evitar bloqueos de API
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "X-Fsign": "SW9D1e1L"  # Firma requerida por los servidores de Flashscore
}

# --- 1. FUNCIÓN DE ENVÍO A TELEGRAM ---
def enviar_resumen_telegram(df):
    TOKEN = "892395866:AAES1dc4LAsedUKUsGR4p5D1SkaMt7nKyes"
    CHAT_ID = "7272170952"  

    if not df.empty:
        mensaje = f"🚀 *ACTUALIZACIÓN EN VIVO* 🚀\n🕒 _Hora:_ {time.strftime('%H:%M:%S')}\n\n"
        
        for _, fila in df.iterrows():
            mensaje += f"⚽ *{fila['Partido en Vivo']}*\n"
            mensaje += f"🏆 *Marcador:* `{fila['Marcador']}` | *Min:* `{fila['Minuto']}`\n"
            mensaje += f"💰 *Betano:* [1: {fila['Betano 1']}] [X: {fila['Betano X']}] [2: {fila['Betano 2']}]\n"
            
            stats_disponibles = []
            columnas_fijas = ["Partido en Vivo", "Marcador", "Tiempo/Estado", "Minuto", "Betano 1", "Betano X", "Betano 2"]
            for col in df.columns:
                if col not in columnas_fijas and fila[col] != "-":
                    stats_disponibles.append(f"• {col}: {fila[col]}")
            
            if stats_disponibles:
                mensaje += "\n".join(stats_disponibles[:6]) + "\n"
            
            mensaje += "───────────────────\n"
        
        try:
            requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}, timeout=10)
            st.toast("✅ Resumen enviado con éxito a Telegram", icon="✉️")
        except Exception:
            pass

# --- 2. EXTRACCIÓN DE DATOS API (PROCESAMIENTO INTERNO) ---
def obtener_datos_partido_api(id_partido):
    datos = {"Betano 1": "-", "Betano X": "-", "Betano 2": "-", "Stats": {}}
    
    # URL del feed de cuotas directo de Flashscore para el partido
    url_cuotas = f"https://2.ds.flashscore.com.br/v1/b/e/odds_1x2_live_{id_partido}_pe_1"
    # URL del feed de estadísticas directo de Flashscore para el partido
    url_stats = f"https://2.ds.flashscore.com.br/v1/b/e/stats_{id_partido}_0"
    
    # 2.1 Extracción de las 3 columnas de cuotas de Betano
    try:
        res_cuotas = requests.get(url_cuotas, headers=HEADERS, timeout=4)
        if res_cuotas.status_code == 200:
            json_cuotas = res_cuotas.json()
            # Buscamos el ID de casa de apuestas correspondiente a Betano (ID: 660)
            for bookmaker in json_cuotas.get("odds", []):
                if bookmaker.get("bookmaker_id") == 660:
                    datos["Betano 1"] = str(bookmaker.get("odds_1", "-"))
                    datos["Betano X"] = str(bookmaker.get("odds_x", "-"))
                    datos["Betano 2"] = str(bookmaker.get("odds_2", "-"))
                    break
    except:
        pass

    # 2.2 Extracción de estadísticas de juego
    try:
        res_stats = requests.get(url_stats, headers=HEADERS, timeout=4)
        if res_stats.status_code == 200:
            json_stats = res_stats.json()
            for grupo in json_stats.get("stages", []):
                for stat in grupo.get("stats", []):
                    nombre_stat = stat.get("name", "Métrica")
                    datos["Stats"][f"{nombre_stat} (L)"] = str(stat.get("home_value", "0"))
                    datos["Stats"][f"{nombre_stat} (V)"] = str(stat.get("away_value", "0"))
    except:
        pass
        
    return datos

# --- 3. CONTENEDOR DINÁMICO AUTOMÁTICO (FRAGMENT) ---
@st.fragment
def contenedor_monitoreo_vivo():
    st.caption(f"🔄 Última actualización de la API: **{time.strftime('%H:%M:%S')}** (Escaneo cada 1 min)")
    tabla_placeholder = st.empty()
    
    try:
        # Petición al feed general en directo de Flashscore Peru
        url_feed_vivo = "https://www.flashscore.pe/"
        response = requests.get(url_feed_vivo, headers=HEADERS, timeout=5)
        
        if response.status_code != 200:
            st.error("Error al conectar con el servidor de datos de Flashscore.")
            return
            
        json_feed = response.json()
        lista_registros_finales = []
        
        # Procesamos los primeros 8 partidos del feed en directo
        partidos_activos = json_feed.get("matches", [])[:8]
        
        if not partidos_activos:
            st.warning("No se encontraron encuentros activos EN DIRECTO en este momento.")
            return
            
        for partido in partidos_activos:
            id_partido = partido.get("id")
            nom_local = partido.get("home_team", "Local")
            nom_visitante = partido.get("away_team", "Visitante")
            
            marcador_home = partido.get("home_score", "0")
            marcador_away = partido.get("away_score", "0")
            minuto_actual = partido.get("status_time", "-")
            estado_juego = partido.get("status_name", "En Vivo")
            
            # Consultamos los feeds internos de cuotas y estadísticas por ID
            detalles = obtener_datos_partido_api(id_partido)
            
            registro = {
                "Partido en Vivo": f"{nom_local} vs {nom_visitante}",
                "Marcador": f"{marcador_home} - {marcador_away}",
                "Tiempo/Estado": estado_juego,
                "Minuto": f"{minuto_actual}'" if minuto_actual.isdigit() else minuto_actual,
                "Betano 1": detalles["Betano 1"],
                "Betano X": detalles["Betano X"],
                "Betano 2": detalles["Betano 2"]
            }
            registro.update(detalles["Stats"])
            lista_registros_finales.append(registro)
            
        if lista_registros_finales:
            df_final = pd.DataFrame(lista_registros_finales).fillna("-")
            columnas_fijas = ["Partido en Vivo", "Marcador", "Tiempo/Estado", "Minuto", "Betano 1", "Betano X", "Betano 2"]
            columnas_stats = [col for col in df_final.columns if col not in columnas_fijas]
            df_final = df_final[columnas_fijas + columnas_stats]
            
            tabla_placeholder.dataframe(df_final, use_container_width=True)
            enviar_resumen_telegram(df_final)
            
    except Exception as e:
        st.error(f"Error en la sincronización de datos: {str(e)}")

    time.sleep(60)
    st.rerun()

# --- 4. RENDERIZADO PRINCIPAL ---
st.write("### 📈 Cuadro de Control General (Actualización Automática)")
contenedor_monitoreo_vivo()
