import hashlib
import io
import os
import re
from datetime import date
from xml.sax.saxutils import escape

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from scipy.stats import linregress

st.set_page_config(page_title="Cinética química", page_icon="⚛", layout="wide")

FUENTE = "Computer Modern Serif, serif"

st.markdown("""
<style>
@import url('https://cdn.jsdelivr.net/gh/dreampulse/computer-modern-web-font@master/fonts.css');
.stApp, .stApp p, .stApp label, .stApp li, .stApp h1, .stApp h2, .stApp h3, .stApp h4,
.stApp input, .stApp textarea, .stApp button, .stApp [data-testid="stMetricValue"],
.stApp [data-testid="stMetricLabel"], .stApp [data-testid="stCaptionContainer"] {
    font-family: 'Computer Modern Serif', serif !important;
}
.stApp p, .stApp label, .stApp li { font-size: 1.08rem; }

.stApp, .stApp p, .stApp label, .stApp li, .stApp h1, .stApp h2, .stApp h3, .stApp h4,
.stApp [data-testid="stMetricValue"], .stApp [data-testid="stMetricLabel"],
.stApp [data-testid="stCaptionContainer"] { color: #000 !important; }
.stApp h2 { margin-top: 2.2rem; }
footer { visibility: hidden; }

/* Cajas con borde: esquinas rectas y línea negra */
div[data-testid="stVerticalBlockBorderWrapper"] {
    border: 1px solid #000 !important; border-radius: 0 !important; }

/* Tabla editable: esquinas rectas y marco oscuro */
div[data-testid="stDataFrame"], div[data-testid="stDataFrame"] > div,
div[data-testid="stDataFrameResizable"] { border-radius: 0 !important; }
div[data-testid="stDataFrame"] { border: 1.5px solid #000 !important; }

/* Tablas de resultados (estilo libro) */
.bloque-tabla { background: #fff; color: #000; padding: 12px 10px 6px 10px; margin: 0.5rem 0 0.4rem 0; overflow-x: auto; }
.bloque-tabla .leyenda-tabla { text-align: center; font-size: 0.98rem; margin-bottom: 0.6rem; }
table.tabla-libro { border-collapse: collapse; margin: 0 auto 0.4rem auto; font-size: 1.02rem; }
table.tabla-libro thead tr { border-top: 2px solid #000; border-bottom: 1px solid #000; }
table.tabla-libro tbody tr:last-child { border-bottom: 2px solid #000; }
table.tabla-libro th, table.tabla-libro td { padding: 5px 20px; text-align: center; border: none; background: #fff; color: #000; }
table.tabla-libro th { font-weight: bold; }
</style>
""", unsafe_allow_html=True)


def formatear_tabla(df, formatos=None):
    """Copia de la tabla con las columnas numéricas convertidas a texto con su formato."""
    formatos = formatos or {}
    d = df.copy()
    for col in d.columns:
        if pd.api.types.is_numeric_dtype(d[col]):
            d[col] = d[col].map(lambda v, f=formatos.get(col, ".4g"): format(v, f))
    return d


def tabla_libro(df, leyenda, nombre, formatos=None):
    """Tabla de tres líneas (negra sobre blanco) con botones para exportarla."""
    exportar = df.copy()
    exportar.columns = [str(c).replace("<br>", " ") for c in exportar.columns]
    d = formatear_tabla(df, formatos)
    html = d.to_html(index=False, escape=False, border=0, classes="tabla-libro")
    html = "".join(linea.strip() for linea in html.splitlines())
    st.markdown(f"<div class='bloque-tabla'><div class='leyenda-tabla'><b>{leyenda}</b></div>{html}</div>",
                unsafe_allow_html=True)
    b1, b2, _ = st.columns([1.3, 1.3, 5])
    buf = io.BytesIO()
    exportar.to_excel(buf, index=False)
    b1.download_button("Descargar Excel", buf.getvalue(), file_name=f"{nombre}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       key=f"xlsx_{nombre}")
    b2.download_button("Descargar CSV", exportar.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
                       file_name=f"{nombre}.csv", mime="text/csv", key=f"csv_{nombre}")
    st.write("")


def estilo_ejes(fig, titulo, xt, yt, x_range=None, y_range=None):
    """Estilo de revista científica: fondo blanco, todo negro, marco completo, una sola fuente."""
    eje = dict(showgrid=False, zeroline=False, showline=True, mirror=True,
               linecolor="black", linewidth=1.5, ticks="inside", ticklen=5,
               tickcolor="black", tickfont=dict(family=FUENTE, size=14, color="black"))
    fig.update_layout(
        font=dict(family=FUENTE, size=15, color="black"),
        title=dict(text=titulo, x=0.5, xanchor="center",
                   font=dict(family=FUENTE, size=17, color="black")),
        height=400, margin=dict(t=90, b=50, l=60, r=20),
        showlegend=False, plot_bgcolor="white", paper_bgcolor="white",
        xaxis=dict(title=dict(text=xt, font=dict(family=FUENTE, size=16, color="black")),
                   range=x_range, **eje),
        yaxis=dict(title=dict(text=yt, font=dict(family=FUENTE, size=16, color="black")),
                   range=y_range, **eje))
    return fig


def mostrar(fig, nombre):
    """Muestra el gráfico (una sola vez); el botón de cámara descarga un PNG de alta resolución."""
    st.plotly_chart(fig, use_container_width=True, theme=None, key=f"pl_{nombre}",
                    config={"displaylogo": False,
                            "toImageButtonOptions": {"format": "png", "filename": nombre,
                                                     "width": 900, "height": 600, "scale": 4}})


def caja(titulo, valor_html, ecuacion=None):
    """Cuadro con borde (como los de tiempo de vida media y tiempos de utilidad)."""
    with st.container(border=True):
        st.markdown(f"<div style='text-align:center; font-weight:bold; min-height:3rem'>{titulo}</div>",
                    unsafe_allow_html=True)
        if ecuacion:
            st.latex(ecuacion)
        st.markdown(f"<div style='text-align:center; padding:0.5rem 0 0.2rem 0'>{valor_html}</div>",
                    unsafe_allow_html=True)


def limpiar_tabla(clave):
    """Vacía la tabla y reinicia el cargador de archivos asociado."""
    st.session_state[f"vacio_{clave}"] = True
    st.session_state[f"v_{clave}"] = st.session_state.get(f"v_{clave}", 0) + 1


def restaurar_ejemplo(clave):
    st.session_state[f"vacio_{clave}"] = False
    st.session_state[f"v_{clave}"] = st.session_state.get(f"v_{clave}", 0) + 1


# ---- Encabezado con logo ----
col_logo, col_titulo = st.columns([1, 5], vertical_alignment="center")
with col_logo:
    if os.path.exists("logo.png"):
        st.image("logo.png", width=120)
with col_titulo:
    st.markdown("<h1 style='margin:0; padding:0'>Proyección de estabilidad de principios activos y análisis cinético de degradación</h1>",
                unsafe_allow_html=True)
    st.caption("Fisicoquímica · Universidad de Antioquia · 2026-2")
st.markdown("---")

# ---------------- CÁLCULOS ----------------
# Fracción de [A] remanente para cada tiempo característico
REMANENTE = {"t50": 0.50, "t98": 0.98, "t95": 0.95, "t90": 0.90}

ORDENES = {
    0: {"nombre": "Orden cero", "eje_y": "[A]"},
    1: {"nombre": "Orden uno", "eje_y": "ln[A]"},
    2: {"nombre": "Orden dos", "eje_y": "1/[A]"},
}


def transformar(orden, c):
    if orden == 0:
        return c
    if orden == 1:
        return np.log(c)
    return 1 / c


def ajustar(orden, t, c):
    """Regresión lineal del orden indicado. Devuelve un diccionario con resultados."""
    y = transformar(orden, c)
    reg = linregress(t, y)
    pendiente, intercepto, r2 = reg.slope, reg.intercept, reg.rvalue ** 2

    if orden in (0, 1):
        k = -pendiente
    else:
        k = pendiente

    # Concentración inicial estimada a partir del intercepto
    if orden == 0:
        a0 = intercepto
    elif orden == 1:
        a0 = np.exp(intercepto)
    else:
        a0 = 1 / intercepto if intercepto != 0 else np.nan

    return {"orden": orden, "y": y, "pendiente": pendiente,
            "intercepto": intercepto, "r2": r2, "k": k, "a0": a0}


def tiempo(orden, k, a0, r):
    """Tiempo para que quede la fracción r de [A]."""
    if not (k > 0) or not (a0 > 0):
        return np.nan
    if orden == 0:
        return (1 - r) * a0 / k
    if orden == 1:
        return -np.log(r) / k
    return (1 / r - 1) / (k * a0)


def leer_archivo(f):
    """Lee un CSV o Excel: columna 1 = tiempo, columna 2 = concentración."""
    if f.name.lower().endswith(".csv"):
        df = pd.read_csv(f, sep=None, engine="python")
    else:
        df = pd.read_excel(f)
    df = df.iloc[:, :2].copy()
    df.columns = ["Tiempo", "Concentración"]
    for col in df.columns:
        df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", ".", regex=False),
                                errors="coerce")
    return df.dropna()


def grafico(t, c, ajuste, unidad_t="h", unidad_c="mg/mL"):
    o = ajuste["orden"]
    etiquetas_y = {0: "[A]", 1: "Ln [A]", 2: "1/[A]"}
    simbolos = {0: "circle", 1: "diamond", 2: "triangle-up"}   # orden 0, 1 y 2

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=t, y=ajuste["y"], mode="markers",
                             marker=dict(size=10, color="black", symbol=simbolos[o])))
    t_lin = np.linspace(t.min(), t.max(), 100)
    fig.add_trace(go.Scatter(x=t_lin, y=ajuste["pendiente"] * t_lin + ajuste["intercepto"],
                             mode="lines", line=dict(color="black", width=1.5, dash="dash")))
    signo = "+" if ajuste["intercepto"] >= 0 else "-"
    ecuacion = f"y = {ajuste['pendiente']:.4g}x {signo} {abs(ajuste['intercepto']):.4g}"

    y_all = ajuste["y"]
    y_pad = (y_all.max() - y_all.min()) * 0.12 or 1
    titulo = f"{ORDENES[o]['nombre']}<br><sup>{ecuacion} | R² = {ajuste['r2']:.4f}</sup>"
    return estilo_ejes(fig, titulo, f"Tiempo ({unidad_t})", etiquetas_y[o],
                       [0, t.max() * 1.08], [y_all.min() - y_pad, y_all.max() + y_pad])


# ---------------- INTERFAZ ----------------

st.header("Entrada de datos")
col_a, _ = st.columns([1, 1])

with col_a:
    cu1, cu2 = st.columns(2)
    unidad_t = cu1.text_input("Unidad de tiempo", "h")
    unidad_c = cu2.text_input("Unidad de concentración", "mg/mL")

    v_d = st.session_state.get("v_datos", 0)
    vacio_d = st.session_state.get("vacio_datos", False)

    archivo = st.file_uploader(
        "O suba un archivo CSV/Excel (col. 1 = tiempo, col. 2 = concentración)",
        type=["csv", "xlsx"], key=f"archivo_datos_{v_d}",
        help="La primera fila debe ser el encabezado (por ejemplo: Tiempo, Concentración).")

    datos_ejemplo = pd.DataFrame({
        "Tiempo": [0.0, 10.0, 20.0, 30.0, 40.0, 50.0],
        "Concentración": [100.0, 82.0, 67.1, 54.8, 45.0, 36.9],
    })
    datos_vacios = pd.DataFrame({"Tiempo": pd.Series(dtype=float),
                                 "Concentración": pd.Series(dtype=float)})
    base = datos_vacios if vacio_d else datos_ejemplo
    nombre_arch = ""
    if archivo is not None:
        try:
            base = leer_archivo(archivo)
            nombre_arch = archivo.name
            st.success(f"Archivo cargado: {archivo.name} ({len(base)} filas)")
        except Exception as e:
            st.error(f"No se pudo leer el archivo ({e}). Se muestra la tabla de ejemplo.")

    st.write("Escriba los datos en la tabla o péguelos desde una hoja de cálculo (se pueden agregar filas):")
    # La clave cambia con el archivo y con los botones para que la tabla se actualice
    datos = st.data_editor(base, num_rows="dynamic", use_container_width=True,
                           key=f"datos_{v_d}_{nombre_arch}_{int(vacio_d)}")
    bd1, bd2, _ = st.columns([1, 1.3, 2])
    bd1.button("Limpiar tabla", on_click=limpiar_tabla, args=("datos",), key="btn_limpiar_datos")
    bd2.button("Restaurar ejemplo", on_click=restaurar_ejemplo, args=("datos",), key="btn_ejemplo_datos")

datos = datos.dropna().sort_values("Tiempo")
t = datos["Tiempo"].to_numpy(dtype=float)
c = datos["Concentración"].to_numpy(dtype=float)

if len(datos) < 3:
    st.warning("Ingrese al menos 3 puntos para hacer el análisis.")
    st.stop()
if np.any(c <= 0):
    st.error("Todas las concentraciones deben ser mayores que 0 (se necesita ln[A] y 1/[A]).")
    st.stop()

# Ajustes de los tres órdenes
ajustes = {o: ajustar(o, t, c) for o in (0, 1, 2)}

st.header("1. Determinación del orden de reacción por el método integral y generación de gráficos")

# Tabla resumen de datos transformados
tabla_t = pd.DataFrame({
    "Tiempo": t,
    "Orden 0<br>[A]": c,
    "Orden 1<br>ln[A]": np.log(c),
    "Orden 2<br>1/[A]": 1 / c,
})
tabla_libro(tabla_t, "Tabla 1. Datos experimentales y transformados", "tabla_1_datos")

g1, g2, g3 = st.columns(3)
for col, o in zip((g1, g2, g3), (0, 1, 2)):
    with col:
        mostrar(grafico(t, c, ajustes[o], unidad_t, unidad_c), f"orden_{o}_ajuste_lineal")

unidades_m = {0: f"{unidad_c}/{unidad_t}", 1: f"1/{unidad_t}", 2: f"1/({unidad_c}·{unidad_t})"}

st.subheader("Resumen de los ajustes lineales")
tabla = pd.DataFrame({
    "Modelo": [ORDENES[o]["nombre"] for o in (0, 1, 2)],
    "Gráfico": [f"{ORDENES[o]['eje_y']} vs t" for o in (0, 1, 2)],
    "Pendiente (m)": [ajustes[o]["pendiente"] for o in (0, 1, 2)],
    "Intercepto (b)": [ajustes[o]["intercepto"] for o in (0, 1, 2)],
    "R²": [ajustes[o]["r2"] for o in (0, 1, 2)],
})
tabla_libro(tabla, "Tabla 2. Resumen de los ajustes lineales", "tabla_2_ajustes",
            formatos={"Pendiente (m)": ".5g", "Intercepto (b)": ".5g", "R²": ".5f"})
st.caption("Unidades de la pendiente: "
           + "; ".join(f"{ORDENES[o]['nombre'].lower()}, {unidades_m[o]}" for o in (0, 1, 2)) + ".")

# Orden más probable: mayor R² entre los que dan k positiva
validos = {o: a for o, a in ajustes.items() if a["k"] > 0}
if not validos:
    st.error("Ningún modelo dio una constante k positiva. Revise los datos.")
    st.stop()
mejor = max(validos, key=lambda o: validos[o]["r2"])
a = ajustes[mejor]

st.header("2. Orden de reacción más probable")
st.success(f"Modelo más probable: **{ORDENES[mejor]['nombre']}** (R² = {a['r2']:.5f})")

# Aviso si hay ambigüedad
otros = sorted([v["r2"] for o, v in validos.items() if o != mejor], reverse=True)
ambiguo = bool(otros) and (a["r2"] - otros[0]) < 0.005
if ambiguo:
    st.warning("Los R² son muy parecidos entre modelos; con estos datos la elección del orden es poco concluyente.")

unidad_k = unidades_m[mejor]
a0_ref = c[0] if abs(t[0]) < 1e-12 else a["a0"]
tiempos = {n: tiempo(mejor, a["k"], a0_ref, r) for n, r in REMANENTE.items()}

st.subheader("Constante cinética (kₐ)")
if mejor in (0, 1):
    st.latex(rf"m = -k_a \;\;\Rightarrow\;\; k_a = -m = {-a['pendiente']:.5g}")
else:
    st.latex(rf"m = k_a \;\;\Rightarrow\;\; k_a = m = {a['pendiente']:.5g}")
ck, _ = st.columns([1, 3], gap="large")
with ck:
    caja("Constante cinética (kₐ)",
         f"<span style='font-size:1.9rem'>{a['k']:.5g}</span><br>"
         f"<span style='font-size:1.1rem'>{unidad_k}</span>")

NOMBRES = {"t50": "Tiempo de vida media (t1/2)", "t90": "Tiempo de utilidad (t90)",
           "t95": "Tiempo de utilidad (t95)", "t98": "Tiempo de utilidad (t98)"}
ECUACIONES = {
    0: {"principal": r"[A]_t = -k_a\,t + [A]_{t=0}",
        "t50": r"t_{1/2} = \dfrac{0.5\,[A]_{t=0}}{k_a}",
        "t90": r"t_{90} = \dfrac{0.10\,[A]_{t=0}}{k_a}",
        "t95": r"t_{95} = \dfrac{0.05\,[A]_{t=0}}{k_a}",
        "t98": r"t_{98} = \dfrac{0.02\,[A]_{t=0}}{k_a}"},
    1: {"principal": r"\ln[A]_t = -k_a\,t + \ln[A]_{t=0}",
        "t50": r"t_{1/2} = \dfrac{0.693}{k_a}",
        "t90": r"t_{90} = \dfrac{0.105}{k_a}",
        "t95": r"t_{95} = \dfrac{0.0513}{k_a}",
        "t98": r"t_{98} = \dfrac{0.0202}{k_a}"},
    2: {"principal": r"\dfrac{1}{[A]_t} = k_a\,t + \dfrac{1}{[A]_{t=0}}",
        "t50": r"t_{1/2} = \dfrac{1}{[A]_{t=0}\,k_a}",
        "t90": r"t_{90} = \dfrac{0.111}{[A]_{t=0}\,k_a}",
        "t95": r"t_{95} = \dfrac{0.0526}{[A]_{t=0}\,k_a}",
        "t98": r"t_{98} = \dfrac{0.0204}{[A]_{t=0}\,k_a}"},
}

st.subheader("Tiempo de vida media y tiempos de utilidad")
st.write(f"Ecuación integrada de {ORDENES[mejor]['nombre'].lower()}:")
st.latex(ECUACIONES[mejor]["principal"])
st.caption(f"[A]t=0 = {a0_ref:.5g} {unidad_c} (dato experimental a t = 0).")

cols = st.columns(4, gap="large")
for col, n in zip(cols, ("t50", "t90", "t95", "t98")):
    with col:
        caja(NOMBRES[n], f"<span style='font-size:1.9rem'>{tiempos[n]:.4g} {unidad_t}</span>",
             ecuacion=ECUACIONES[mejor][n])

# =====================================================
# 3. MÓDULO ARRHENIUS
# =====================================================
R_GAS = 8.314  # J/(mol·K)


def leer_archivo_arr(f):
    """CSV/Excel: columna 1 = temperatura, columna 2 = k."""
    if f.name.lower().endswith(".csv"):
        df = pd.read_csv(f, sep=None, engine="python")
    else:
        df = pd.read_excel(f)
    df = df.iloc[:, :2].copy()
    df.columns = ["Temperatura", "k"]
    for col in df.columns:
        df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", ".", regex=False),
                                errors="coerce")
    return df.dropna()


st.header("3. Módulo Arrhenius")
st.write("Ecuación de Arrhenius:")
st.latex(r"k = A\,e^{-E_a/RT}")
st.write("Forma linealizada (recta y = mx + b):")
st.latex(r"\ln k = -\dfrac{E_a}{R}\times\dfrac{1}{T} + \ln A \qquad\qquad m = -\dfrac{E_a}{R}")
st.write("Ingrese las constantes k obtenidas a diferentes temperaturas "
         "(todas del mismo orden de reacción y con las mismas unidades).")

v_a = st.session_state.get("v_arr", 0)
vacio_a = st.session_state.get("vacio_arr", False)

ca1, ca2 = st.columns(2)
with ca1:
    unidad_T = st.radio("Unidad de temperatura", ["°C", "K"], horizontal=True)
    archivo_arr = st.file_uploader(
        "O suba un archivo CSV/Excel (col. 1 = temperatura, col. 2 = k)",
        type=["csv", "xlsx"], key=f"archivo_arr_{v_a}",
        help="La primera fila debe ser el encabezado (por ejemplo: Temperatura, k).")
arr_ejemplo = pd.DataFrame({
    "Temperatura": [40.0, 50.0, 60.0, 70.0],
    "k": [0.0021, 0.0058, 0.0148, 0.0360],
})
arr_vacio = pd.DataFrame({"Temperatura": pd.Series(dtype=float), "k": pd.Series(dtype=float)})
arr_base = arr_vacio if vacio_a else arr_ejemplo
nombre_arr = ""
if archivo_arr is not None:
    try:
        arr_base = leer_archivo_arr(archivo_arr)
        nombre_arr = archivo_arr.name
        ca1.success(f"Archivo cargado: {archivo_arr.name} ({len(arr_base)} filas)")
    except Exception as e:
        ca1.error(f"No se pudo leer el archivo ({e}). Se muestra la tabla de ejemplo.")
with ca2:
    arr = st.data_editor(arr_base, num_rows="dynamic", use_container_width=True,
                         key=f"arrhenius_{v_a}_{nombre_arr}_{int(vacio_a)}")
    ba1, ba2, _ = st.columns([1, 1.3, 2])
    ba1.button("Limpiar tabla", on_click=limpiar_tabla, args=("arr",), key="btn_limpiar_arr")
    ba2.button("Restaurar ejemplo", on_click=restaurar_ejemplo, args=("arr",), key="btn_ejemplo_arr")

arr = arr.dropna()
if len(arr) < 3:
    st.warning("Ingrese al menos 3 pares (temperatura, k) para el análisis de Arrhenius.")
    st.stop()

offset = 273.15 if unidad_T == "°C" else 0.0
T_user = arr["Temperatura"].to_numpy(dtype=float)
T_K = T_user + offset
k_arr = arr["k"].to_numpy(dtype=float)
if np.any(k_arr <= 0) or np.any(T_K <= 0):
    st.error("Todas las k deben ser > 0 y las temperaturas deben ser válidas (T > 0 K).")
    st.stop()

inv_T = 1 / T_K
ln_k = np.log(k_arr)
reg_arr = linregress(inv_T, ln_k)
Ea = -reg_arr.slope * R_GAS          # J/mol
A_pre = np.exp(reg_arr.intercept)    # factor preexponencial (mismas unidades que k)
r2_arr = reg_arr.rvalue ** 2

# --- Gráfico 1: k vs T ---
pad_T = (T_user.max() - T_user.min()) * 0.08 or 1
T_c = np.linspace(T_user.min(), T_user.max(), 100)
k_c = A_pre * np.exp(-Ea / (R_GAS * (T_c + offset)))
fig_k = go.Figure()
fig_k.add_trace(go.Scatter(x=T_user, y=k_arr, mode="markers",
                           marker=dict(size=10, color="black", symbol="square")))
fig_k.add_trace(go.Scatter(x=T_c, y=k_c, mode="lines", line=dict(color="black", width=1.5, dash="dash")))
estilo_ejes(fig_k, "k vs T<br><sup>k = A·e^(−Ea/RT)</sup>", f"Temperatura ({unidad_T})", "k",
            [T_user.min() - pad_T, T_user.max() + pad_T], [0, k_arr.max() * 1.12])

# --- Gráfico 2: ln k vs 1/T ---
signo = "+" if reg_arr.intercept >= 0 else "-"
ecuacion = f"y = {reg_arr.slope:.5g}x {signo} {abs(reg_arr.intercept):.5g}"
pad_x = (inv_T.max() - inv_T.min()) * 0.08 or 1e-5
pad_y = (ln_k.max() - ln_k.min()) * 0.12 or 1
x_l = np.linspace(inv_T.min(), inv_T.max(), 100)
fig_lin = go.Figure()
fig_lin.add_trace(go.Scatter(x=inv_T, y=ln_k, mode="markers",
                             marker=dict(size=10, color="black", symbol="square")))
fig_lin.add_trace(go.Scatter(x=x_l, y=reg_arr.slope * x_l + reg_arr.intercept,
                             mode="lines", line=dict(color="black", width=1.5, dash="dash")))
estilo_ejes(fig_lin, f"ln k vs 1/T<br><sup>{ecuacion} | R² = {r2_arr:.4f}</sup>",
            "1/T (K⁻¹)", "ln k",
            [inv_T.min() - pad_x, inv_T.max() + pad_x], [ln_k.min() - pad_y, ln_k.max() + pad_y])
fig_lin.update_xaxes(tickformat=".2e")

gk, gl = st.columns(2)
with gk:
    mostrar(fig_k, "arrhenius_k_vs_T")
with gl:
    mostrar(fig_lin, "arrhenius_lnk_vs_inv_T")

# --- Pendiente, Ea y A ---
st.latex(rf"m = -\dfrac{{E_a}}{{R}} = {reg_arr.slope:.5g}\ \text{{K}}"
         rf"\;\;\Rightarrow\;\; E_a = -m\,R = {Ea/1000:.2f}\ \text{{kJ/mol}}")

tabla_arr = pd.DataFrame({
    "T (K)": T_K, "1/T (1/K)": inv_T, "k": k_arr, "ln k": ln_k,
})
tabla_libro(tabla_arr, "Tabla 3. Datos para el gráfico de Arrhenius", "tabla_3_arrhenius",
            formatos={"T (K)": ".2f", "1/T (1/K)": ".4e", "k": ".5g", "ln k": ".4f"})

ar_cols = st.columns(5, gap="large")
resultados_arr = [
    ("Ea (kJ/mol)", f"{Ea/1000:.2f}"),
    ("Ea (kcal/mol)", f"{Ea/4184:.2f}"),
    ("ln A (intercepto)", f"{reg_arr.intercept:.4f}"),
    ("Factor preexponencial A", f"{A_pre:.4e}"),
    ("R² Arrhenius", f"{r2_arr:.4f}"),
]
for col, (titulo_r, valor_r) in zip(ar_cols, resultados_arr):
    with col:
        caja(titulo_r, f"<span style='font-size:1.6rem'>{valor_r}</span>")
st.caption("A tiene las mismas unidades de k.")
if r2_arr < 0.95:
    st.warning("El R² de Arrhenius es bajo; la predicción puede no ser confiable.")

# =====================================================
# 4. PREDICCIÓN DE ESTABILIDAD
# =====================================================
st.header("4. Predicción de estabilidad")

orden_pred = st.selectbox(
    "Orden de reacción para la predicción",
    [0, 1, 2], index=mejor,
    format_func=lambda o: ORDENES[o]["nombre"] + (" (detectado en la sección 2)" if o == mejor else ""),
    key=f"orden_pred_{mejor}",
    help="Por defecto se usa el orden detectado. Se puede cambiar para comparar.")
if orden_pred != mejor:
    st.warning(f"Se está usando {ORDENES[orden_pred]['nombre'].lower()} y no el detectado "
               f"({ORDENES[mejor]['nombre'].lower()}). Las k de la sección 3 deben corresponder a ese orden.")

cp1, cp2, cp3 = st.columns(3)
with cp1:
    T_ref = st.number_input(f"Temperatura de referencia ({unidad_T})",
                            value=25.0 if unidad_T == "°C" else 298.15)
with cp2:
    txt_temps = st.text_input(f"Temperaturas a predecir ({unidad_T}), separadas por coma",
                              "4, 25, 30, 40" if unidad_T == "°C" else "277, 298, 303, 313")
with cp3:
    a0_pred = st.number_input(f"Concentración inicial ({unidad_c})", value=float(c[0]))

try:
    temps_pred = [float(x) for x in txt_temps.replace(";", ",").split(",") if x.strip()]
except ValueError:
    st.error("Escriba las temperaturas solo con números separados por comas.")
    st.stop()

todas = [T_ref] + [x for x in temps_pred if x != T_ref]


def k_en(T_usuario):
    return A_pre * np.exp(-Ea / (R_GAS * (T_usuario + offset)))


k_ref = k_en(T_ref)
filas = []
for T_u in todas:
    k_T = k_en(T_u)
    fila = {f"T ({unidad_T})": T_u, "k": k_T, "k / k_ref": k_T / k_ref}
    for n, r in REMANENTE.items():
        fila[f"{n} ({unidad_t})"] = tiempo(orden_pred, k_T, a0_pred, r)
    fila["t90 vs ref."] = tiempo(orden_pred, k_T, a0_pred, 0.90) / tiempo(orden_pred, k_ref, a0_pred, 0.90)
    filas.append(fila)
pred = pd.DataFrame(filas)

vista = pd.DataFrame({
    f"T ({unidad_T})": pred[f"T ({unidad_T})"],
    "k": pred["k"],
    f"Tiempo de vida media (t1/2) ({unidad_t})": pred[f"t50 ({unidad_t})"],
    f"Tiempo de utilidad (t98) ({unidad_t})": pred[f"t98 ({unidad_t})"],
    f"Tiempo de utilidad (t95) ({unidad_t})": pred[f"t95 ({unidad_t})"],
    f"Tiempo de utilidad (t90) ({unidad_t})": pred[f"t90 ({unidad_t})"],
})
tabla_libro(vista, "Tabla 4. Predicción de k y de los tiempos característicos", "tabla_4_prediccion")
st.caption("La primera fila es la temperatura de referencia.")

T_min_exp, T_max_exp = T_K.min() - offset, T_K.max() - offset
fuera = [x for x in todas if x < T_min_exp or x > T_max_exp]
if fuera:
    st.warning(f"Extrapolación: {fuera} está fuera del rango experimental "
               f"({T_min_exp:.1f} a {T_max_exp:.1f} {unidad_T}). La predicción es menos confiable.")

# =====================================================
# 5. CONCLUSIONES AUTOMÁTICAS
# =====================================================
st.header("5. Conclusiones automáticas")

# ---- Datos clave para las conclusiones ----
T_ref_K = T_ref + offset
Q10 = k_en(T_ref + 10) / k_en(T_ref)          # cuánto aumenta k por cada +10 °C (o +10 K)
t90_ref = tiempo(mejor, k_ref, a0_pred, 0.90)
t50_ref = tiempo(mejor, k_ref, a0_pred, 0.50)
fila_ref = pred.iloc[0]
otras = pred.iloc[1:]


def clasificar_ea(ea_kj):
    if ea_kj < 40:
        return "baja (la velocidad de degradación depende poco de la temperatura)"
    if ea_kj <= 100:
        return "moderada, típica de la degradación de fármacos (la temperatura influye de forma notable)"
    return "alta (la degradación es muy sensible a la temperatura)"


def conclusion_por_reglas():
    L = []
    # 1. Orden cinético
    L.append(f"**Orden de reacción.** Los datos se ajustan mejor a una cinética de "
             f"**{ORDENES[mejor]['nombre'].lower()}** (R² = {a['r2']:.4f}), con "
             f"k = {a['k']:.4g} {unidad_k}.")
    otros_r2 = {ORDENES[o]['nombre']: v['r2'] for o, v in ajustes.items() if o != mejor}
    L.append("Los R² de los otros modelos fueron " +
             ", ".join(f"{n}: {r:.4f}" for n, r in otros_r2.items()) + ".")
    segundo = max(otros_r2.values())
    if a["r2"] - segundo < 0.005:
        L.append("La diferencia entre modelos es muy pequeña; se recomienda más puntos "
                 "experimentales o una mayor conversión para confirmar el orden.")
    if len(t) < 5:
        L.append("Se usaron pocos puntos (menos de 5), lo que reduce la confiabilidad del ajuste.")
    # 2. Tiempos característicos
    L.append(f"**Tiempos característicos (a la temperatura del ensayo).** "
             f"t98 = {tiempos['t98']:.4g} {unidad_t}, t95 = {tiempos['t95']:.4g} {unidad_t}, "
             f"t90 = {tiempos['t90']:.4g} {unidad_t} y t50 = {tiempos['t50']:.4g} {unidad_t}.")
    # 3. Arrhenius
    L.append(f"**Dependencia con la temperatura.** La energía de activación es "
             f"**{Ea/1000:.1f} kJ/mol** ({Ea/4184:.1f} kcal/mol), un valor {clasificar_ea(Ea/1000)}. "
             f"El ajuste de Arrhenius tiene R² = {r2_arr:.4f}. "
             f"Por cada aumento de 10 {unidad_T} a partir de {T_ref:g} {unidad_T}, la velocidad de "
             f"degradación se multiplica por aproximadamente **{Q10:.2f}**.")
    if r2_arr < 0.95:
        L.append("El R² de Arrhenius es bajo: el mecanismo podría cambiar con la temperatura "
                 "o los datos tienen error, por lo que las predicciones son poco confiables.")
    # 4. Predicción
    L.append(f"**Predicción de estabilidad.** A la temperatura de referencia ({T_ref:g} {unidad_T}) "
             f"el t90 estimado es {t90_ref:.4g} {unidad_t}.")
    if len(otras) > 0:
        col_T, col_t90 = f"T ({unidad_T})", f"t90 ({unidad_t})"
        mas_fria = otras.loc[otras[col_T].idxmin()]
        mas_calida = otras.loc[otras[col_T].idxmax()]
        L.append(f"A {mas_fria[col_T]:g} {unidad_T} el t90 sería {mas_fria[col_t90]:.4g} {unidad_t} "
                 f"({mas_fria['t90 vs ref.']:.2f} veces el de referencia), y a "
                 f"{mas_calida[col_T]:g} {unidad_T} sería {mas_calida[col_t90]:.4g} {unidad_t} "
                 f"({mas_calida['t90 vs ref.']:.2f} veces el de referencia).")
    if fuera:
        L.append(f"Algunas temperaturas ({fuera}) están fuera del rango experimental "
                 f"({T_min_exp:.1f} a {T_max_exp:.1f} {unidad_T}); es una extrapolación.")
    L.append("*Estas conclusiones son una estimación a partir de los datos ingresados y deben "
             "confirmarse con estudios de estabilidad.*")
    return "\n\n".join(L)


texto_reglas = conclusion_por_reglas()
st.subheader("Conclusión automática")
st.markdown(texto_reglas)


# ---- Conclusión con IA ----
@st.cache_data(show_spinner=False, ttl=3600)
def generar_ia(clave, modelo, prompt):
    """Llama a Groq (API compatible con OpenAI). Si falla, prueba un modelo de respaldo. Falla rápido."""
    errores = []
    for m in dict.fromkeys([modelo, "openai/gpt-oss-20b"]):
        try:
            cuerpo = {"model": m, "temperature": 0.2, "max_tokens": 3000,
                      "messages": [{"role": "user", "content": prompt}]}
            if "gpt-oss" in m:
                cuerpo["reasoning_effort"] = "low"   # razona poco: responde antes y no gasta el límite
            r = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {clave}", "Content-Type": "application/json"},
                json=cuerpo, timeout=20)
            if r.status_code != 200:
                raise RuntimeError(f"{r.status_code} {r.text[:150]}")
            return r.json()["choices"][0]["message"]["content"]
        except Exception as e:
            errores.append(f"[{m}] {e}")
    raise RuntimeError(" | ".join(errores))


def clave_ia():
    """Lee la clave guardada como secreto (el visitante no escribe nada)."""
    try:
        return st.secrets["GROQ_API_KEY"]
    except Exception:
        return ""


st.subheader("Conclusión con IA")
farmaco = st.text_input("Nombre del fármaco o producto (opcional)", "")
with st.expander("Opciones avanzadas"):
    clave_propia = st.text_input("Usar una clave propia de Groq (opcional)", type="password")
    modelo = st.text_input("Modelo", "openai/gpt-oss-120b")
clave = clave_propia or clave_ia()

if st.button("Generar conclusión con IA"):
    if not clave:
        st.error("La IA no está disponible en este momento. Use la conclusión automática por reglas de arriba.")
    elif st.session_state.get("n_ia", 0) >= 5 and not clave_propia:
        st.warning("Se alcanzó el máximo de 5 conclusiones con IA por sesión. "
                   "Use la conclusión por reglas o una clave propia en Opciones avanzadas.")
    else:
        otros_r2 = ", ".join(f"{ORDENES[o]['nombre']} = {v['r2']:.4f}" for o, v in ajustes.items() if o != mejor)
        perdida = (c[0] - c[-1]) / c[0] * 100
        col_T, col_t90 = f"T ({unidad_T})", f"t90 ({unidad_t})"
        p_fria = pred.loc[pred[col_T].idxmin()]
        p_calida = pred.loc[pred[col_T].idxmax()]
        if p_fria[col_T] != p_calida[col_T]:
            comparacion = (f"t90 a {p_fria[col_T]:g} {unidad_T} = {p_fria[col_t90]:.4g} {unidad_t}; "
                           f"t90 a {p_calida[col_T]:g} {unidad_T} = {p_calida[col_t90]:.4g} {unidad_t}; "
                           f"relación = {p_fria[col_t90] / p_calida[col_t90]:.3g} veces")
        else:
            comparacion = "solo se predijo una temperatura"
        prompt = f"""Eres profesor de fisicoquímica farmacéutica. Redacta en español la conclusión de un análisis cinético en 2 párrafos de prosa continua más una frase final (sin listas, sin viñetas, sin títulos).

ESTILO
- Lenguaje lacónico y técnico, como en las diapositivas de clase: frases cortas y directas, sin adornos.
- Coma decimal (0,54) y cada valor con su unidad. Escribe t1/2, t90, t95 y t98 en texto plano.
- Usa los términos: ingrediente funcional, concentración inicial, método integral, coeficiente de determinación (R²), constante cinética (ka), tiempo de vida media (t1/2), tiempo de utilidad, energía de activación (Ea).
- Sin adjetivos de valoración ("rápida", "significativamente", "gran estabilidad"). Concluye con números y comparaciones, no con adjetivos.
- Máximo 200 palabras en total.

DEFINICIONES CORRECTAS (no las cambies)
- t1/2: tiempo en que se ha degradado el 50 % de la concentración inicial del ingrediente funcional.
- t90: tiempo en que se ha degradado el 10 % (queda el 90 %). t95: se ha degradado el 5 %. t98: se ha degradado el 2 %.
- Nunca digas que t90 es "el 90 % de degradación".

ESTRUCTURA
Párrafo 1 (resultados): orden de reacción y R² por el método integral, comparado con los R² de los otros modelos; ka con su unidad; t1/2, t90 y t95 con su definición; relaciona la degradación alcanzada con la duración del ensayo.
Si la diferencia entre los R² es menor a 0,005, escribe: "Dado que los coeficientes de determinación son muy próximos, no es posible determinar el orden real de la reacción", y menciona la poca degradación.
Párrafo 2 (análisis): Ea con el R² de Arrhenius y el número de temperaturas usadas; cómo cambia el t90 entre la temperatura más baja y la más alta predichas (usa la relación dada); t90 a la temperatura de referencia frente al t90 del ensayo. Si los datos muestran que el t90 aumenta al bajar la temperatura, dilo como resultado, sin suponer condiciones como refrigeración. Limitación: menciona la extrapolación solo si en los datos dice "sí"; aclara que el t90 estimado debe confirmarse con un estudio de estabilidad.
Frase final (conclusión): una sola frase que integre orden de reacción, ka, t90 a la temperatura de referencia y la tendencia del t90 con la temperatura.

MODELO DE REDACCIÓN (sustituye por los datos reales; no copies los números)
"La cinética de degradación corresponde a orden [X] (R² = [..]) frente a [otros R²], con ka = [..] [unidad]. t1/2 = [..] [unidad]: tiempo en que se ha degradado el 50 % de la concentración inicial del ingrediente funcional. t90 = [..] [unidad] corresponde a una degradación del 10 %, y t95 = [..] [unidad] a una del 5 %. En el ensayo se degradó [..] % en [..] [unidad]. La energía de activación obtenida por la ecuación de Arrhenius es Ea = [..] kJ/mol (R² = [..], [n] temperaturas). El t90 pasa de [..] [unidad] a [T1] °C a [..] [unidad] a [T2] °C ([..] veces)."

DATOS (usa solo estos; no inventes valores, mecanismos ni referencias)
Fármaco: {farmaco or 'no especificado'}
Puntos experimentales: {len(t)}; duración del ensayo: {t[-1] - t[0]:g} {unidad_t}
Degradación alcanzada en el ensayo: {perdida:.1f} %
Orden de reacción: {ORDENES[mejor]['nombre']} (R² = {a['r2']:.4f})
R² de los otros modelos: {otros_r2}
Constante cinética: ka = {a['k']:.4g} {unidad_k}
t1/2 = {tiempos['t50']:.4g} {unidad_t}; t90 = {tiempos['t90']:.4g} {unidad_t}; t95 = {tiempos['t95']:.4g} {unidad_t}; t98 = {tiempos['t98']:.4g} {unidad_t}
Arrhenius: Ea = {Ea/1000:.1f} kJ/mol; A = {A_pre:.3e}; R² = {r2_arr:.4f}; temperaturas usadas: {len(T_K)}
A {T_ref:g} {unidad_T}: t90 = {t90_ref:.4g} {unidad_t}
Comparación entre temperaturas predichas: {comparacion}
Extrapolación fuera del rango experimental: {'sí' if fuera else 'no'}"""
        try:
            with st.spinner("Generando conclusión..."):
                st.session_state["texto_ia"] = generar_ia(clave, modelo, prompt)
            if not clave_propia:
                st.session_state["n_ia"] = st.session_state.get("n_ia", 0) + 1
        except Exception as e:
            st.error("No se pudo generar la conclusión con IA en este momento. "
                     "Use la conclusión automática por reglas de arriba.")
            st.caption(f"Detalle técnico: {e}")

if "texto_ia" in st.session_state:
    st.markdown(st.session_state["texto_ia"])

# ---- Descarga de conclusiones ----
informe = "CONCLUSIÓN POR REGLAS\n\n" + texto_reglas.replace("**", "").replace("*", "")
if "texto_ia" in st.session_state:
    informe += "\n\nCONCLUSIÓN CON IA\n\n" + st.session_state["texto_ia"]
st.download_button("Descargar conclusiones (.txt)", informe, file_name="conclusiones_estabilidad.txt")


# =====================================================
# INFORME COMPLETO EN PDF
# =====================================================
def generar_pdf(x):
    """Arma el informe completo en PDF (tablas, gráficos, ecuaciones y conclusiones)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FormatStrFormatter
    from PIL import Image as PILImage
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (Image, KeepTogether, Paragraph, SimpleDocTemplate,
                                    Spacer, Table, TableStyle)

    # --- Fuente serif con soporte de ², ⁻¹, ·, etc. (viene con matplotlib) ---
    ruta = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")
    try:
        pdfmetrics.registerFont(TTFont("STIX", os.path.join(ruta, "STIXGeneral.ttf")))
        pdfmetrics.registerFont(TTFont("STIX-B", os.path.join(ruta, "STIXGeneralBol.ttf")))
        pdfmetrics.registerFont(TTFont("STIX-I", os.path.join(ruta, "STIXGeneralItalic.ttf")))
        pdfmetrics.registerFont(TTFont("STIX-BI", os.path.join(ruta, "STIXGeneralBolIta.ttf")))
        pdfmetrics.registerFontFamily("STIX", normal="STIX", bold="STIX-B",
                                      italic="STIX-I", boldItalic="STIX-BI")
        f_n, f_b = "STIX", "STIX-B"
    except Exception:
        f_n, f_b = "Times-Roman", "Times-Bold"

    est_cuerpo = ParagraphStyle("cuerpo", fontName=f_n, fontSize=10.5, leading=14.5,
                                alignment=TA_JUSTIFY, spaceAfter=6)
    est_titulo = ParagraphStyle("titulo", fontName=f_b, fontSize=17, leading=21, spaceAfter=4)
    est_sub = ParagraphStyle("sub", fontName=f_n, fontSize=10.5, leading=14, textColor=colors.HexColor("#333333"))
    est_h = ParagraphStyle("h", fontName=f_b, fontSize=13, leading=16, spaceBefore=14, spaceAfter=6,
                           keepWithNext=True)
    est_h3 = ParagraphStyle("h3", fontName=f_b, fontSize=11, leading=14, spaceBefore=8, spaceAfter=4,
                            keepWithNext=True)
    est_ley = ParagraphStyle("ley", fontName=f_b, fontSize=9.5, leading=12, alignment=TA_CENTER,
                             spaceBefore=6, spaceAfter=4, keepWithNext=True)
    est_cel = ParagraphStyle("cel", fontName=f_n, fontSize=9, leading=11, alignment=TA_CENTER)
    est_nota = ParagraphStyle("nota", fontName=f_n, fontSize=9, leading=11.5, alignment=TA_CENTER,
                              textColor=colors.HexColor("#333333"), spaceAfter=6)

    ANCHO = A4[0] - 4 * cm

    def md(txt):
        s = escape(txt)
        s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
        s = re.sub(r"\*(.+?)\*", r"<i>\1</i>", s)
        return s

    def parrafos(txt):
        return [Paragraph(md(p).replace("\n", "<br/>"), est_cuerpo)
                for p in txt.split("\n\n") if p.strip()]

    estilo_3l = TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 1.2, colors.black),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.black),
        ("LINEBELOW", (0, -1), (-1, -1), 1.2, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)])

    def tabla_pdf(df, leyenda, formatos=None, anchos=None):
        d = formatear_tabla(df, formatos)
        enc = [Paragraph(f"<b>{escape(str(col).replace('<br>', ' '))}</b>", est_cel) for col in d.columns]
        cuerpo = [[Paragraph(escape(str(v)), est_cel) for v in fila] for fila in d.itertuples(index=False)]
        anchos = anchos or [ANCHO / len(d.columns)] * len(d.columns)
        tb = Table([enc] + cuerpo, colWidths=anchos, hAlign="CENTER")
        tb.setStyle(estilo_3l)
        return KeepTogether([Paragraph(escape(leyenda), est_ley), tb, Spacer(1, 8)])

    def ecuacion_img(latex, tam=12):
        latex = latex.replace(r"\dfrac", r"\frac")
        with plt.rc_context({"mathtext.fontset": "stix", "font.family": "STIXGeneral"}):
            fig = plt.figure(figsize=(0.1, 0.1))
            fig.text(0, 0, f"${latex}$", fontsize=tam)
            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=300, bbox_inches="tight", pad_inches=0.03)
            plt.close(fig)
        buf.seek(0)
        w, h = PILImage.open(io.BytesIO(buf.getvalue())).size
        return Image(buf, width=w * 72 / 300, height=h * 72 / 300)

    def figura(xd, yd, xf, yf, marcador, titulo, subtitulo, xl, yl, xlim, ylim, fmt_x=None):
        with plt.rc_context({"font.family": "STIXGeneral", "mathtext.fontset": "stix"}):
            fig, ax = plt.subplots(figsize=(4.2, 3.4))
            ax.plot(xd, yd, linestyle="none", marker=marcador, color="black", markersize=6)
            ax.plot(xf, yf, linestyle="--", color="black", linewidth=1.2)
            ax.set_xlim(xlim)
            ax.set_ylim(ylim)
            ax.set_xlabel(xl, fontsize=11)
            ax.set_ylabel(yl, fontsize=11)
            ax.tick_params(direction="in", top=True, right=True, labelsize=9, length=4)
            for sp in ax.spines.values():
                sp.set_linewidth(1.2)
            if fmt_x:
                ax.xaxis.set_major_formatter(FormatStrFormatter(fmt_x))
                ax.locator_params(axis="x", nbins=4)
            ax.set_title(titulo, fontsize=11.5, pad=24)
            ax.text(0.5, 1.03, subtitulo, transform=ax.transAxes, ha="center", va="bottom", fontsize=8.5)
            fig.tight_layout()
            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=250)
            plt.close(fig)
        buf.seek(0)
        ancho = 8.4 * cm
        return Image(buf, width=ancho, height=ancho * 3.4 / 4.2)

    def fila_imgs(imgs):
        tb = Table([imgs], colWidths=[8.5 * cm] * len(imgs), hAlign="CENTER")
        tb.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
        return tb

    ORD, NOM, ECU = x["ORDENES"], x["NOMBRES"], x["ECUACIONES"]
    t_, c_, ajustes_ = x["t"], x["c"], x["ajustes"]
    mejor_, a_ = x["mejor"], x["a"]
    ut, uc, uT = x["unidad_t"], x["unidad_c"], x["unidad_T"]
    story = []

    # ---- Encabezado ----
    titulo = [Paragraph("Proyección de estabilidad de principios activos y análisis cinético de degradación", est_titulo),
              Paragraph("Informe de análisis · Fisicoquímica · Universidad de Antioquia · 2026-2", est_sub),
              Paragraph(f"Fecha: {date.today().strftime('%d/%m/%Y')}", est_sub)]
    if x.get("logo") and os.path.exists(x["logo"]):
        lw, lh = PILImage.open(x["logo"]).size
        logo = Image(x["logo"], width=2.4 * cm, height=2.4 * cm * lh / lw)
        enc = Table([[logo, titulo]], colWidths=[3 * cm, ANCHO - 3 * cm])
        enc.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        story.append(enc)
    else:
        story += titulo
    story.append(Spacer(1, 10))
    datos_gen = f"Unidad de tiempo: {escape(ut)}. Unidad de concentración: {escape(uc)}."
    if x.get("farmaco"):
        datos_gen = f"Fármaco o producto: <b>{escape(x['farmaco'])}</b>. " + datos_gen
    story.append(Paragraph(datos_gen, est_cuerpo))

    # ---- 1. Orden de reacción ----
    story.append(Paragraph("1. Determinación del orden de reacción por el método integral", est_h))
    story.append(tabla_pdf(x["tabla_t"], "Tabla 1. Datos experimentales y transformados"))

    simbolos = {0: "o", 1: "D", 2: "^"}
    figs = []
    for o in (0, 1, 2):
        aj = ajustes_[o]
        yy = aj["y"]
        pad = (yy.max() - yy.min()) * 0.12 or 1
        tl = np.linspace(t_.min(), t_.max(), 100)
        sg = "+" if aj["intercepto"] >= 0 else "-"
        figs.append(figura(
            t_, yy, tl, aj["pendiente"] * tl + aj["intercepto"], simbolos[o], ORD[o]["nombre"],
            f"y = {aj['pendiente']:.4g}x {sg} {abs(aj['intercepto']):.4g}  |  R² = {aj['r2']:.4f}",
            f"Tiempo ({ut})", {0: "[A]", 1: "Ln [A]", 2: "1/[A]"}[o],
            (0, t_.max() * 1.08), (yy.min() - pad, yy.max() + pad)))
    story.append(fila_imgs(figs[:2]))
    story.append(fila_imgs(figs[2:]))
    story.append(Paragraph("Figura 1. Linealización de los datos para orden cero, uno y dos.", est_nota))

    story.append(tabla_pdf(x["tabla2"], "Tabla 2. Resumen de los ajustes lineales",
                           formatos={"Pendiente (m)": ".5g", "Intercepto (b)": ".5g", "R²": ".5f"}))
    um = x["unidades_m"]
    story.append(Paragraph("Unidades de la pendiente: " + "; ".join(
        f"{ORD[o]['nombre'].lower()}, {escape(um[o])}" for o in (0, 1, 2)) + ".", est_nota))

    # ---- 2. Orden más probable ----
    story.append(Paragraph("2. Orden de reacción más probable", est_h))
    story.append(Paragraph(f"Modelo más probable: <b>{ORD[mejor_]['nombre']}</b> (R² = {a_['r2']:.5f}).", est_cuerpo))
    if x["ambiguo"]:
        story.append(Paragraph("Los R² son muy parecidos entre modelos; con estos datos la elección del orden "
                               "es poco concluyente.", est_cuerpo))
    story.append(Paragraph(f"Constante cinética: k<sub>a</sub> = <b>{a_['k']:.5g} {escape(x['unidad_k'])}</b>.",
                           est_cuerpo))
    story.append(Paragraph(f"Ecuación integrada de {ORD[mejor_]['nombre'].lower()}:", est_cuerpo))
    story.append(ecuacion_img(ECU[mejor_]["principal"], 13))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"[A]<sub>t=0</sub> = {x['a0_ref']:.5g} {escape(uc)} (dato experimental a t = 0).",
                           est_cuerpo))
    filas_t = [[Paragraph("<b>Tiempo característico</b>", est_cel), Paragraph("<b>Ecuación</b>", est_cel),
                Paragraph(f"<b>Valor ({escape(ut)})</b>", est_cel)]]
    for n in ("t50", "t90", "t95", "t98"):
        filas_t.append([Paragraph(escape(NOM[n]), est_cel), ecuacion_img(ECU[mejor_][n], 11),
                        Paragraph(f"{x['tiempos'][n]:.4g}", est_cel)])
    tb_t = Table(filas_t, colWidths=[6.5 * cm, 6 * cm, 3.5 * cm], hAlign="CENTER")
    tb_t.setStyle(estilo_3l)
    story.append(KeepTogether([Paragraph("Tiempo de vida media y tiempos de utilidad", est_ley), tb_t,
                               Spacer(1, 8)]))

    # ---- 3. Arrhenius ----
    story.append(Paragraph("3. Módulo Arrhenius", est_h))
    story.append(ecuacion_img(r"k = A\,e^{-E_a/RT}", 13))
    story.append(Spacer(1, 3))
    story.append(ecuacion_img(r"\ln k = -\frac{E_a}{R}\times\frac{1}{T} + \ln A \qquad m = -\frac{E_a}{R}", 13))
    story.append(Spacer(1, 6))

    T_user_, inv_T_, ln_k_, k_arr_ = x["T_user"], x["inv_T"], x["ln_k"], x["k_arr"]
    off = x["offset"]
    Ea_, A_, reg = x["Ea"], x["A_pre"], x["reg_arr"]
    pT = (T_user_.max() - T_user_.min()) * 0.08 or 1
    Tc = np.linspace(T_user_.min(), T_user_.max(), 100)
    kc = A_ * np.exp(-Ea_ / (R_GAS * (Tc + off)))
    fig1 = figura(T_user_, k_arr_, Tc, kc, "s", "k vs T", "k = A·exp(−Ea/RT)",
                  f"Temperatura ({uT})", "k",
                  (T_user_.min() - pT, T_user_.max() + pT), (0, k_arr_.max() * 1.12))
    px = (inv_T_.max() - inv_T_.min()) * 0.08 or 1e-5
    py = (ln_k_.max() - ln_k_.min()) * 0.12 or 1
    xl_ = np.linspace(inv_T_.min(), inv_T_.max(), 100)
    sg = "+" if reg.intercept >= 0 else "-"
    fig2 = figura(inv_T_, ln_k_, xl_, reg.slope * xl_ + reg.intercept, "s", "ln k vs 1/T",
                  f"y = {reg.slope:.5g}x {sg} {abs(reg.intercept):.5g}  |  R² = {x['r2_arr']:.4f}",
                  r"1/T (K$^{-1}$)", "ln k", (inv_T_.min() - px, inv_T_.max() + px),
                  (ln_k_.min() - py, ln_k_.max() + py), fmt_x="%.2e")
    story.append(fila_imgs([fig1, fig2]))
    story.append(Paragraph("Figura 2. Dependencia de k con la temperatura y linealización de Arrhenius.", est_nota))
    story.append(ecuacion_img(
        rf"m = -\frac{{E_a}}{{R}} = {reg.slope:.5g}\ \mathrm{{K}}\ \Rightarrow\ "
        rf"E_a = -mR = {Ea_/1000:.2f}\ \mathrm{{kJ/mol}}", 12))
    story.append(Spacer(1, 6))
    story.append(tabla_pdf(x["tabla_arr"], "Tabla 3. Datos para el gráfico de Arrhenius",
                           formatos={"T (K)": ".2f", "1/T (1/K)": ".4e", "k": ".5g", "ln k": ".4f"}))
    res = pd.DataFrame({
        "Parámetro": ["Ea (kJ/mol)", "Ea (kcal/mol)", "ln A (intercepto)", "Factor preexponencial A",
                      "R² Arrhenius"],
        "Valor": [f"{Ea_/1000:.2f}", f"{Ea_/4184:.2f}", f"{reg.intercept:.4f}", f"{A_:.4e}",
                  f"{x['r2_arr']:.4f}"]})
    story.append(tabla_pdf(res, "Parámetros de Arrhenius", anchos=[7 * cm, 5 * cm]))
    story.append(Paragraph("A tiene las mismas unidades de k.", est_nota))
    if x["r2_arr"] < 0.95:
        story.append(Paragraph("El R² de Arrhenius es bajo; la predicción puede no ser confiable.", est_cuerpo))

    # ---- 4. Predicción ----
    story.append(Paragraph("4. Predicción de estabilidad", est_h))
    story.append(Paragraph(
        f"Orden de reacción usado: {ORD[x['orden_pred']]['nombre']}. Temperatura de referencia: "
        f"{x['T_ref']:g} {escape(uT)}. Concentración inicial: {x['a0_pred']:g} {escape(uc)}.", est_cuerpo))
    story.append(tabla_pdf(x["vista"], "Tabla 4. Predicción de k y de los tiempos característicos",
                           anchos=[2 * cm, 2.6 * cm, 3.1 * cm, 3.1 * cm, 3.1 * cm, 3.1 * cm]))
    story.append(Paragraph("La primera fila es la temperatura de referencia.", est_nota))
    if x["fuera"]:
        story.append(Paragraph(
            f"Extrapolación: {x['fuera']} está fuera del rango experimental "
            f"({x['T_min_exp']:.1f} a {x['T_max_exp']:.1f} {escape(uT)}). La predicción es menos confiable.",
            est_cuerpo))

    # ---- 5. Conclusiones ----
    story.append(Paragraph("5. Conclusiones", est_h))
    story.append(Paragraph("Conclusión automática", est_h3))
    story += parrafos(x["texto_reglas"])
    if x.get("texto_ia"):
        story.append(Paragraph("Conclusión con IA", est_h3))
        story += parrafos(x["texto_ia"])

    def pie(canvas, doc):
        canvas.saveState()
        canvas.setFont(f_n, 8.5)
        canvas.drawString(2 * cm, 1.2 * cm, "Universidad de Antioquia · Fisicoquímica CIFAL · 2026-2")
        canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Página {doc.page}")
        canvas.restoreState()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=1.8 * cm, bottomMargin=2 * cm,
                            title="Informe de análisis cinético y estabilidad")
    doc.build(story, onFirstPage=pie, onLaterPages=pie)
    return buf.getvalue()


st.subheader("Informe completo en PDF")
firma = hashlib.md5(repr((
    np.round(t, 8).tolist(), np.round(c, 8).tolist(), np.round(T_user, 8).tolist(),
    np.round(k_arr, 10).tolist(), unidad_t, unidad_c, unidad_T, orden_pred, float(T_ref),
    txt_temps, float(a0_pred), farmaco, st.session_state.get("texto_ia", ""))).encode()).hexdigest()

if st.button("Generar informe PDF", key="btn_pdf"):
    try:
        with st.spinner("Generando informe..."):
            ctx = dict(
                ORDENES=ORDENES, NOMBRES=NOMBRES, ECUACIONES=ECUACIONES, t=t, c=c, ajustes=ajustes,
                mejor=mejor, a=a, unidad_t=unidad_t, unidad_c=unidad_c, unidad_T=unidad_T,
                unidad_k=unidad_k, unidades_m=unidades_m, tabla_t=tabla_t, tabla2=tabla,
                ambiguo=ambiguo, a0_ref=a0_ref, tiempos=tiempos, T_user=T_user, inv_T=inv_T,
                ln_k=ln_k, k_arr=k_arr, offset=offset, Ea=Ea, A_pre=A_pre, reg_arr=reg_arr,
                r2_arr=r2_arr, tabla_arr=tabla_arr, vista=vista, orden_pred=orden_pred,
                T_ref=T_ref, a0_pred=a0_pred, fuera=fuera, T_min_exp=T_min_exp,
                T_max_exp=T_max_exp, texto_reglas=texto_reglas,
                texto_ia=st.session_state.get("texto_ia", ""), farmaco=farmaco, logo="logo.png")
            st.session_state["pdf_bytes"] = generar_pdf(ctx)
            st.session_state["pdf_firma"] = firma
    except Exception as e:
        st.error("No se pudo generar el informe en PDF.")
        st.caption(f"Detalle técnico: {e}")

if "pdf_bytes" in st.session_state:
    if st.session_state.get("pdf_firma") == firma:
        st.download_button("Descargar informe completo (PDF)", st.session_state["pdf_bytes"],
                           file_name="informe_cinetica_estabilidad.pdf", mime="application/pdf",
                           key="dl_pdf")
    else:
        st.caption("Los datos cambiaron desde el último informe: genere el informe de nuevo.")

st.markdown("---")
st.caption("Universidad de Antioquia · Fisicoquímica CIFAL · 2026-2  \n"
           "Diseñado por: L. Hernández, J. Hincapie, X. Lopera, P. Medina")