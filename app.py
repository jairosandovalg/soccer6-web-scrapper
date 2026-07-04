import streamlit as st
import pandas as pd
import time
import requests
from bs4 import BeautifulSoup

# Configuración de la interfaz de Streamlit
st.set_page_config(page_title="Bot de Estadísticas Final", layout="wide")
st.title("📊 Monitor de Estadísticas en Vivo - Flashscore & Telegram")
st.subheader("Análisis de métricas en tiempo real con alertas automatizadas y cuotas de Betano")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
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

# --- 2. EXTRACCIÓN DE DETALLES (ESTADÍSTICAS Y CUOTAS DE BETANO) ---
def extraer_detalles_partido(id_partido):
    detalles = {"Betano 1": "-", "Betano X": "-", "Betano 2": "-", "Stats": {}}
    
    # Usamos la URL web estándar de Flashscore para evitar caídas de subdominios de la API
    url_match = f"https://www.flashscore.pe/partido/{id_partido}/#/resumen/estadisticas"
    
    try:
        res = requests.get(url_match, headers=HEADERS, timeout=5)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # Buscar el bloque interactivo de cuotas que compartiste en tu HTML
            fila_betano = soup.find("div", {"data-analytics-element": "ODDS_COMPARISONS_INTERACTIVE_ROW"})
            if fila_betano and "Betano" in str(fila_betano):
                celdas = fila_betano.find_all("span", {"data-testid": "wcl-oddsValue"})
                if len(celdas) >= 3:
                    detalles["Betano 1"] = celdas[0].text.strip()
                    detalles["Betano X"] = celdas[1].text.strip()
                    detalles["Betano 2"] = celdas[2].text.strip()
            
            # Buscar estadísticas dinámicas en el árbol HTML
            bloques_stats = soup.find_all("div", {"data-testid": "wcl-statistics"})
            for bloque in bloques_stats:
                try:
                    cat = bloque.find("div", {"data-testid": "wcl-statistics-category"}).text.strip()
                    home_val = bloque.find("div", class_=lambda x: x and 'wcl-homeValue' in x).text.strip()
                    away_val = bloque.find("div", class_=lambda x: x and 'wcl-awayValue' in x).text.strip()
                    
                    detalles["Stats"][f"{cat} (L)"] = home_val
                    detalles["Stats"][f"{cat} (V)"] = away_val
                except:
                    pass
    except:
        pass
    return detalles

# --- 3. CONTENEDOR DINÁMICO AUTOMÁTICO (FRAGMENT) ---
@st.fragment
def contenedor_monitoreo_vivo():
    st.caption(f"🔄 Última actualización: **{time.strftime('%H:%M:%S')}** (Escaneo automático cada 1 min)")
    tabla_placeholder = st.empty()
    
    try:
        # Cargamos el HTML de la página de inicio que muestra los partidos EN DIRECTO
        url_principal = "https://www.flashscore.pe/"
        res_main = requests.get(url_principal, headers=HEADERS, timeout=6)
        
        if res_main.status_code != 200:
            st.error("No se pudo conectar con el servidor principal de Flashscore.")
            return
            
        soup_main = BeautifulSoup(res_main.text, 'html.parser')
        
        # Flashscore identifica los partidos en vivo usando divs cuyos IDs empiezan con 'g_1_'
        partidos = [div for div in soup_main.find_all("div") if div.get("id") and div.get("id").startswith("g_1_")]
        
        if not partidos:
            st.warning("No se detectaron partidos activos EN DIRECTO en este momento.")
            return
            
        lista_registros_finales = []
        
        # Escaneamos los primeros 8 partidos activos en vivo
        for partido in partidos[:8]:
            try:
                id_partido = partido.get("id").split('_')[-1]
                
                # Extraer nombres de equipos buscando las clases de participantes
                nom_local = partido.find("div", class_=lambda x: x and 'home' in x and 'participant' in x).text.strip()
                nom_visitante = partido.find("div", class_=lambda x: x and 'away' in x and 'participant' in x).text.strip()
                
                # Marcadores en vivo
                score_home = partido.find("div", class_=lambda x: x and 'home' in x and 'score' in x).text.strip()
                score_away = partido.find("div", class_=lambda x: x and 'away' in x and 'score' in x).text.strip()
                
                # Minuto actual del partido
                try: minuto = partido.find("div", class_=lambda x: x and 'stage' in x).text.strip()
                except: minuto = "Live"
                
                # Obtener cuotas de Betano y estadísticas mediante parseo HTML directo
                detalles = extraer_detalles_partido(id_partido)
                
                registro = {
                    "Partido en Vivo": f"{nom_local} vs {nom_visitante}",
                    "Marcador": f"{score_home} - {score_away}",
                    "Tiempo/Estado": "En Vivo",
                    "Minuto": minuto,
                    "Betano 1": detalles["Betano 1"],
                    "Betano X": detalles["Betano X"],
                    "Betano 2": detalles["Betano 2"]
                }
                registro.update(detalles["Stats"])
                lista_registros_finales.append(registro)
            except:
                pass
                
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
