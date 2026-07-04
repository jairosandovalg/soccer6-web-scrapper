import os
import sys
import streamlit as st
import pandas as pd
import time
import subprocess
import requests

# --- 1. COMPROBACIÓN E INSTALACIÓN DE PLAYWRIGHT ---
if 'navegador_configurado' not in st.session_state:
    with st.spinner("Iniciando el sistema por única vez..."):
        try:
            # Instalación simple sin tocar el sistema operativo
            subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
            st.session_state['navegador_configurado'] = True
        except Exception as e:
            st.error(f"Error: {str(e)}")
            st.stop()
    from playwright.sync_api import sync_playwright
    st.rerun()

from playwright.sync_api import sync_playwright

st.set_page_config(page_title="Bot de Estadísticas Final", layout="wide")
st.title("📊 Monitor de Estadísticas en Vivo - Flashscore & Telegram")

# --- 2. FUNCIÓN DE ENVÍO A TELEGRAM ---
def enviar_resumen_telegram(df):
    TOKEN = "892395866:AAES1dc4LAsedUKUsGR4p5D1SkaMt7nKyes"
    CHAT_ID = "7272170952"  

    if not df.empty:
        mensaje = f"🚀 *ACTUALIZACIÓN EN VIVO* 🚀\n🕒 _Hora:_ {time.strftime('%H:%M:%S')}\n\n"
        for _, fila in df.iterrows():
            mensaje += f"⚽ *{fila['Partido en Vivo']}*\n"
            mensaje += f"🏆 *Marcador:* `{fila['Marcador']}` | *Min:* `{fila['Minuto']}`\n"
            # Añadido al mensaje de Telegram
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

# --- 3. EXTRACCIÓN DE DATOS DE PARTIDOS ---
def extraer_estadisticas_partido(context, url_partido):
    # Se inicializan los 3 campos solicitados: Local, Empate (X), Visitante
    datos_partido = {
        "Marcador": "- - -", "Tiempo/Estado": "-", "Minuto": "-", 
        "Betano 1": "-", "Betano X": "-", "Betano 2": "-", 
        "Stats": {}
    }
    page = None
    try:
        page = context.new_page()
        page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "font", "stylesheet"] else route.continue_())
        page.goto(url_partido, timeout=7000, wait_until="domcontentloaded")
        
        # Datos principales
        if page.locator("div.detailScore__wrapper").first.count() > 0:
            datos_partido["Marcador"] = page.locator("div.detailScore__wrapper").first.text_content().strip()
        if page.locator("span.fixedHeaderDuel__detailStatus").first.count() > 0:
            datos_partido["Tiempo/Estado"] = page.locator("span.fixedHeaderDuel__detailStatus").first.text_content().strip()
        if page.locator("span.eventTime").first.count() > 0:
            datos_partido["Minuto"] = page.locator("span.eventTime").first.text_content().strip()
            
        # OBTENER EXCLUSIVAMENTE LAS CUOTAS DE BETANO
        boton_cuotas = page.locator("//button[@role='tab' and contains(., 'Cuotas')]").first
        if boton_cuotas.count() > 0:
            boton_cuotas.click(timeout=1000)
            page.wait_for_selector("div[data-analytics-element='ODDS_COMPARISONS_INTERACTIVE_ROW']", timeout=2000)
            
            fila_betano = page.locator("div[data-analytics-element='ODDS_COMPARISONS_INTERACTIVE_ROW']:has(a[title*='Betano'])").first
            if fila_betano.count() > 0:
                celdas_cuotas = fila_betano.locator("span[data-testid='wcl-oddsValue']").all()
                if len(celdas_cuotas) >= 3:
                    datos_partido["Betano 1"] = celdas_cuotas[0].text_content().strip()
                    datos_partido["Betano X"] = celdas_cuotas[1].text_content().strip()
                    datos_partido["Betano 2"] = celdas_cuotas[2].text_content().strip()
            
        # Regresar a Estadísticas habituales
        boton_stats = page.locator("//button[@role='tab' and contains(., 'Estadísticas')]").first
        if boton_stats.count() > 0:
            boton_stats.click(timeout=1000)
            page.wait_for_selector("div[data-testid='wcl-statistics']", timeout=2000)
            for fila in page.locator("div[data-testid='wcl-statistics']").all():
                cat_el = fila.locator("div[data-testid='wcl-statistics-category']").first
                if cat_el.count() > 0:
                    categoria = cat_el.text_content().strip()
                    h_el = fila.locator("div[class*='wcl-homeValue']").first
                    v_el = fila.locator("div[class*='wcl-awayValue']").first
                    datos_partido["Stats"][f"{categoria} (L)"] = h_el.text_content().strip() if h_el.count() > 0 else "0"
                    datos_partido["Stats"][f"{categoria} (V)"] = v_el.text_content().strip() if v_el.count() > 0 else "0"
    except Exception:
        pass
    finally:
        if page: page.close()
    return datos_partido

# --- 4. CONTENEDOR DINÁMICO AUTOMÁTICO ---
@st.fragment
def contenedor_monitoreo_vivo():
    st.caption(f"🔄 Actualización del sistema: **{time.strftime('%H:%M:%S')}**")
    tabla_placeholder = st.empty()
    
    with sync_playwright() as p:
        browser = None
        context = None
        try:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"])
            context = browser.new_context(user_agent="Mozilla/5.0 (Windows) AppleWebKit/537.36")
            main_page = context.new_page()
            main_page.goto("https://www.flashscore.pe/", wait_until="domcontentloaded")
            
            boton_directo = main_page.locator("//div[contains(@class, 'filters__text') and text()='EN DIRECTO']")
            boton_directo.wait_for(state="visible", timeout=10000)
            boton_directo.click()
            
            time.sleep(2.5)
            partidos_elementos = main_page.locator("div[id^='g_1_']").all()
            
            if partidos_elementos:
                lista_registros_finales = []
                for fila in partidos_elementos[:8]:
                    id_partido = fila.get_attribute("id").split('_')[-1]
                    url_match_stats = f"https://www.flashscore.pe/partido/{id_partido}/#/resumen/estadisticas"
                    
                    l_el = fila.locator("div[class*='home'][class*='participant']").first
                    v_el = fila.locator("div[class*='away'][class*='participant']").first
                    nom_local = l_el.text_content().strip() if l_el.count() > 0 else "Local"
                    nom_visita = v_el.text_content().strip() if v_el.count() > 0 else "Visitante"
                    
                    res = extraer_estadisticas_partido(context, url_match_stats)
                    
                    registro = {
                        "Partido en Vivo": f"{nom_local} vs {nom_visita}",
                        "Marcador": res["Marcador"], "Tiempo/Estado": res["Tiempo/Estado"], "Minuto": res["Minuto"],
                        "Betano 1": res["Betano 1"], "Betano X": res["Betano X"], "Betano 2": res["Betano 2"]
                    }
                    registro.update(res["Stats"])
                    lista_registros_finales.append(registro)
                
                if lista_registros_finales:
                    df_final = pd.DataFrame(lista_registros_finales).fillna("-")
                    columnas_fijas = ["Partido en Vivo", "Marcador", "Tiempo/Estado", "Minuto", "Betano 1", "Betano X", "Betano 2"]
                    columnas_stats = [col for col in df_final.columns if col not in columnas_fijas]
                    df_final = df_final[columnas_fijas + columnas_stats]
                    
                    tabla_placeholder.dataframe(df_final, use_container_width=True)
                    enviar_resumen_telegram(df_final)
        except Exception as e:
            st.error(f"Error en navegador: {str(e)}")
        finally:
            if context: context.close()
            if browser: browser.close()

    time.sleep(60)
    st.rerun()

st.write("### 📈 Cuadro de Control General (Actualización Automática)")
contenedor_monitoreo_vivo()
