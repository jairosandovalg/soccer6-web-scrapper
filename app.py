import os
import sys
import streamlit as st
import pandas as pd
import time
import requests

# Cambiamos a las herramientas portátiles de Selenium
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

# Configuración de la interfaz de Streamlit
st.set_page_config(page_title="Bot de Estadísticas Final", layout="wide")
st.title("📊 Monitor de Estadísticas en Vivo - Flashscore & Telegram")
st.subheader("Análisis de métricas en tiempo real con alertas automatizadas")

# --- 1. CONFIGURACIÓN DEL NAVEGADOR PORTABLE ---
def iniciar_navegador():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")  # Modo oculto eficiente para servidores
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    
    # Esto descarga e instala el binario directamente en el entorno de Python, sin tocar Linux
    from webdriver_manager.chrome import ChromeDriverManager
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

# --- 2. FUNCIÓN DE ENVÍO A TELEGRAM ---
def enviar_resumen_telegram(df):
    TOKEN = "892395866:AAES1dc4LAsedUKUsGR4p5D1SkaMt7nKyes"
    CHAT_ID = "7272170952"  

    if not df.empty:
        mensaje = f"🚀 *ACTUALIZACIÓN EN VIVO* 🚀\n🕒 _Hora:_ {time.strftime('%H:%M:%S')}\n\n"
        
        for _, fila in df.iterrows():
            mensaje += f"⚽ *{fila['Partido en Vivo']}*\n"
            mensaje += f"🏆 *Marcador:* `{fila['Marcador']}` | *Min:* `{fila['Minuto']}`\n"
            # Incluimos tus 3 columnas de Betano en el cuerpo del mensaje de Telegram
            mensaje += f"💰 *Betano:* [1: {fila['Betano 1']}] [X: {fila['Betano X']}] [2: {fila['Betano 2']}]\n"
            
            stats_disponibles = []
            columnas_fijas = ["Partido en Vivo", "Marcador", "Tiempo/Estado", "Minuto", "Betano 1", "Betano X", "Betano 2"]
            for col in df.columns:
                if col not in columnas_fijas and fila[col] != "-":
                    stats_disponibles.append(f"• {col}: {fila[col]}")
            
            if stats_disponibles:
                mensaje += "\n".join(stats_disponibles[:6]) + "\n"
            
            mensaje += "───────────────────\n"
        
        url_api = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}
        
        try:
            requests.post(url_api, json=payload, timeout=10)
            st.toast("✅ Resumen enviado con éxito a Telegram", icon="✉️")
        except Exception:
            pass

# --- 3. EXTRACCIÓN DE DATOS DE PARTIDOS ---
def extraer_estadisticas_partido(driver, url_partido):
    # Inicializamos las 3 columnas de Betano solicitadas
    datos_partido = {
        "Marcador": "- - -", "Tiempo/Estado": "-", "Minuto": "-", 
        "Betano 1": "-", "Betano X": "-", "Betano 2": "-", 
        "Stats": {}
    }
    try:
        driver.get(url_partido)
        time.sleep(2)  # Pausa breve para asegurar la carga del DOM
        
        # Datos principales del marcador
        try: datos_partido["Marcador"] = driver.find_element(By.CSS_SELECTOR, "div.detailScore__wrapper").text.replace("\n", " ").strip()
        except: pass
        try: datos_partido["Tiempo/Estado"] = driver.find_element(By.CSS_SELECTOR, "span.fixedHeaderDuel__detailStatus").text.strip()
        except: pass
        try: datos_partido["Minuto"] = driver.find_element(By.CSS_SELECTOR, "span.eventTime").text.strip()
        except: pass
            
        # EXTRAER TUS 3 NUEVOS CAMPOS DESDE LA PESTAÑA CUOTAS
        try:
            boton_cuotas = driver.find_element(By.XPATH, "//button[@role='tab' and contains(., 'Cuotas')]")
            boton_cuotas.click()
            time.sleep(1.2)
            
            # Localizar la fila interactiva de Betano según el código HTML compartido
            fila_betano = driver.find_element(By.XPATH, "//div[@data-analytics-element='ODDS_COMPARISONS_INTERACTIVE_ROW' and .//a[contains(@title, 'Betano')]]")
            celdas_cuotas = fila_betano.find_elements(By.XPATH, ".//span[@data-testid='wcl-oddsValue']")
            
            if len(celdas_cuotas) >= 3:
                datos_partido["Betano 1"] = celdas_cuotas[0].text.strip()
                datos_partido["Betano X"] = celdas_cuotas[1].text.strip()
                datos_partido["Betano 2"] = celdas_cuotas[2].text.strip()
        except:
            pass
            
        # Extraer Estadísticas del partido
        try:
            boton_stats = driver.find_element(By.XPATH, "//button[@role='tab' and contains(., 'Estadísticas')]")
            boton_stats.click()
            time.sleep(1)
            
            filas = driver.find_elements(By.XPATH, "//div[@data-testid='wcl-statistics']")
            for fila in filas:
                try:
                    categoria = fila.find_element(By.XPATH, ".//div[@data-testid='wcl-statistics-category']").text.strip()
                    val_home = fila.find_element(By.XPATH, ".//div[contains(@class, 'wcl-homeValue')]").text.strip()
                    val_away = fila.find_element(By.XPATH, ".//div[contains(@class, 'wcl-awayValue')]").text.strip()
                    
                    datos_partido["Stats"][f"{categoria} (L)"] = val_home
                    datos_partido["Stats"][f"{categoria} (V)"] = val_away
                except:
                    pass
        except:
            pass
            
    except Exception:
        pass
    return datos_partido

# --- 4. CONTENEDOR DINÁMICO AUTOMÁTICO (FRAGMENT) ---
@st.fragment
def contenedor_monitoreo_vivo():
    st.caption(f"🔄 Última actualización: **{time.strftime('%H:%M:%S')}** (Escaneo automático cada 1 min)")
    
    estado_placeholder = st.empty()
    tabla_placeholder = st.empty()

    estado_placeholder.info("Abriendo el navegador virtual en directo...")
    
    driver = None
    try:
        driver = iniciar_navegador()
        driver.get("https://www.flashscore.pe/")
        time.sleep(3)
        
        # Filtrar por EN DIRECTO
        boton_directo = driver.find_element(By.XPATH, "//div[contains(@class, 'filters__text') and text()='EN DIRECTO']")
        boton_directo.click()
        time.sleep(3)
        
        partidos_elementos = driver.find_elements(By.XPATH, "//div[starts-with(@id, 'g_1_')]")
        
        if not partidos_elementos:
            estado_placeholder.warning("No hay encuentros en vivo en este momento.")
        else:
            partidos_filtrados = partidos_elementos[:8] 
            estado_placeholder.success(f"Procesando {len(partidos_filtrados)} partidos activos...")
            
            lista_registros_finales = []
            ids_partidos = []
            
            # Recopilar identificadores fijos para evitar pérdidas de referencia en bucle
            for fila in partidos_filtrados:
                try:
                    id_partido = fila.get_attribute("id").split('_')[-1]
                    local_text = fila.find_element(By.XPATH, ".//div[contains(@class, 'home') and contains(@class, 'participant')]").text.strip()
                    away_text = fila.find_element(By.XPATH, ".//div[contains(@class, 'away') and contains(@class, 'participant')]").text.strip()
                    ids_partidos.append((id_partido, local_text, away_text))
                except:
                    pass
            
            # Escanear métricas individuales por partido
            for id_partido, nom_local, nom_visitante in ids_partidos:
                url_match_stats = f"https://www.flashscore.pe/partido/{id_partido}/#/resumen/estadisticas"
                resultado_profundo = extraer_estadisticas_partido(driver, url_match_stats)
                
                registro = {
                    "Partido en Vivo": f"{nom_local} vs {nom_visitante}",
                    "Marcador": resultado_profundo["Marcador"],
                    "Tiempo/Estado": resultado_profundo["Tiempo/Estado"],
                    "Minuto": resultado_profundo["Minuto"],
                    "Betano 1": resultado_profundo["Betano 1"],
                    "Betano X": resultado_profundo["Betano X"],
                    "Betano 2": resultado_profundo["Betano 2"]
                }
                registro.update(resultado_profundo["Stats"])
                lista_registros_finales.append(registro)
            
            estado_placeholder.empty()
            
            if lista_registros_finales:
                df_final = pd.DataFrame(lista_registros_finales).fillna("-")
                # Posicionar las 3 nuevas columnas al inicio de la tabla interactiva
                columnas_fijas = ["Partido en Vivo", "Marcador", "Tiempo/Estado", "Minuto", "Betano 1", "Betano X", "Betano 2"]
                columnas_stats = [col for col in df_final.columns if col not in columnas_fijas]
                df_final = df_final[columnas_fijas + columnas_stats]
                
                tabla_placeholder.dataframe(df_final, use_container_width=True)
                enviar_resumen_telegram(df_final)
            
    except Exception as e:
        estado_placeholder.error(f"Error durante el escaneo: {str(e)}")
    finally:
        if driver:
            driver.quit()

    time.sleep(60)
    st.rerun()

# --- 5. RENDERIZADO PRINCIPAL ---
st.write("### 📈 Cuadro de Control General (Actualización Automática)")
contenedor_monitoreo_vivo()
