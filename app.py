import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import linregress
import plotly.graph_objects as go

st.set_page_config(page_title="Cinética química", page_icon="⚛", layout="wide")
st.markdown("""
<style>
@import url('https://cdn.jsdelivr.net/gh/dreampulse/computer-modern-web-font@master/fonts.css');
.stApp, .stApp p, .stApp label, .stApp li, .stApp h1, .stApp h2, .stApp h3, .stApp h4,
.stApp input, .stApp textarea, .stApp button, .stApp [data-testid="stMetricValue"],
.stApp [data-testid="stMetricLabel"], .stApp [data-testid="stCaptionContainer"] {
    font-family: 'Computer Modern Serif', serif !important;
}
.stApp p, .stApp label, .stApp li { font-size: 1.08rem; }
</style>
""", unsafe_allow_html=True)
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
    colores = {0: "#1F77B4",   # orden cero: azul
               1: "#FF7F0E",   # orden uno: naranja
               2: "#92D050"}   # orden dos: verde claro
    color = colores[o]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=t, y=ajuste["y"], mode="markers",
                             name="Datos", marker=dict(size=10, color=color)))
    t_lin = np.linspace(t.min(), t.max(), 100)
    fig.add_trace(go.Scatter(x=t_lin, y=ajuste["pendiente"] * t_lin + ajuste["intercepto"],
                             mode="lines", name="Ajuste lineal", line=dict(color=color)))
    signo = "+" if ajuste["intercepto"] >= 0 else "-"
    ecuacion = f"y = {ajuste['pendiente']:.4g}x {signo} {abs(ajuste['intercepto']):.4g}"

    # Rango de los ejes con un pequeño margen
    x_min, x_max = 0, t.max() * 1.08
    y_all = ajuste["y"]
    y_pad = (y_all.max() - y_all.min()) * 0.12 or 1
    y_min, y_max = y_all.min() - y_pad, y_all.max() + y_pad

    fig.update_layout(
        font=dict(family="Computer Modern Serif, serif", size=14),
       title=f"{ORDENES[o]['nombre']}<br><sup>{ecuacion} | R² = {ajuste['r2']:.4f}</sup>",
        xaxis_title=f"Tiempo ({unidad_t})",
        yaxis_title=etiquetas_y[o],
        height=380, margin=dict(t=80, b=40),
        showlegend=False,
        plot_bgcolor="white",
        xaxis=dict(range=[x_min, x_max], showgrid=False, zeroline=False,
                   showline=True, linecolor="black", linewidth=2, ticks="outside"),
        yaxis=dict(range=[y_min, y_max], showgrid=False, zeroline=False,
                   showline=True, linecolor="black", linewidth=2, ticks="outside"),
    )
    return fig


# ---------------- INTERFAZ ----------------
st.title("Análisis cinético y predicción de estabilidad")
st.caption("Fisicoquímica CIFAL, UdeA 2026-2")
st.caption("Diseñado por: P.Medina, L. Hernández, J. Hincapie, X. Lopera")

st.header("1. Ingreso de datos")
col_a, _ = st.columns([1, 1])

with col_a:
    unidad_t = st.text_input("Unidad de tiempo", "h")
    unidad_c = st.text_input("Unidad de concentración", "mg/mL")

    # --- NUEVO: carga de archivo CSV / Excel ---
    archivo = st.file_uploader(
        "…o sube un CSV/Excel (col. 1 = tiempo, col. 2 = concentración)",
        type=["csv", "xlsx"],
        help="La primera fila debe ser el encabezado (por ejemplo: Tiempo, Concentración).")

    datos_ejemplo = pd.DataFrame({
        "Tiempo": [0.0, 10.0, 20.0, 30.0, 40.0, 50.0],
        "Concentración": [100.0, 82.0, 67.1, 54.8, 45.0, 36.9],
    })
    base = datos_ejemplo
    nombre_arch = ""
    if archivo is not None:
        try:
            base = leer_archivo(archivo)
            nombre_arch = archivo.name
            st.success(f"Archivo cargado: {archivo.name} ({len(base)} filas)")
        except Exception as e:
            st.error(f"No pude leer el archivo ({e}). Se muestra la tabla de ejemplo.")

    st.write("Edita la tabla o pega tus datos (puedes agregar filas):")
    # La clave cambia con el archivo para que la tabla se actualice al subir uno nuevo
    datos = st.data_editor(base, num_rows="dynamic", use_container_width=True,
                           key=f"datos_{nombre_arch}")

datos = datos.dropna().sort_values("Tiempo")
t = datos["Tiempo"].to_numpy(dtype=float)
c = datos["Concentración"].to_numpy(dtype=float)

if len(datos) < 3:
    st.warning("Ingresa al menos 3 puntos para hacer el análisis.")
    st.stop()
if np.any(c <= 0):
    st.error("Todas las concentraciones deben ser mayores que 0 (se necesita ln[A] y 1/[A]).")
    st.stop()



# Ajustes de los tres órdenes
ajustes = {o: ajustar(o, t, c) for o in (0, 1, 2)}

st.header("2. Gráficos linealizados")

# Tabla resumen de datos transformados (como en la diapositiva 86)
tabla_t = pd.DataFrame({
    ("", "Tiempo"): t,
    ("Orden 0", "[A]"): c,
    ("Orden 1", "ln[A]"): np.log(c),
    ("Orden 2", "1/[A]"): 1 / c,
})
st.dataframe(tabla_t.style.format("{:.4g}"), use_container_width=True, hide_index=True)

g1, g2, g3 = st.columns(3)
for col, o in zip((g1, g2, g3), (0, 1, 2)):
    with col:
        st.plotly_chart(grafico(t, c, ajustes[o], unidad_t, unidad_c), use_container_width=True)

unidades_m = {0: f"{unidad_c}/{unidad_t}", 1: f"1/{unidad_t}", 2: f"1/({unidad_c}·{unidad_t})"}

st.header("3. Resumen de los ajustes")
tabla = pd.DataFrame({
    "Modelo": [ORDENES[o]["nombre"] for o in (0, 1, 2)],
    "Gráfico": [f"{ORDENES[o]['eje_y']} vs t" for o in (0, 1, 2)],
    "Pendiente (m)": [f"{ajustes[o]['pendiente']:.5g} {unidades_m[o]}" for o in (0, 1, 2)],
    "Intercepto (b)": [ajustes[o]["intercepto"] for o in (0, 1, 2)],
    "R²": [ajustes[o]["r2"] for o in (0, 1, 2)],
})
st.dataframe(tabla.style.format({"Intercepto (b)": "{:.5g}", "R²": "{:.5f}"}),
             use_container_width=True)

# Orden más probable: mayor R² entre los que dan k positiva
validos = {o: a for o, a in ajustes.items() if a["k"] > 0}
if not validos:
    st.error("Ningún modelo dio una constante k positiva. Revisa tus datos.")
    st.stop()
mejor = max(validos, key=lambda o: validos[o]["r2"])
a = ajustes[mejor]

st.header("4. Orden de reacción y parámetros cinéticos")
st.success(f"Modelo más probable: **{ORDENES[mejor]['nombre']}** (R² = {a['r2']:.5f})")

# Aviso si hay ambigüedad
otros = sorted([v["r2"] for o, v in validos.items() if o != mejor], reverse=True)
if otros and (a["r2"] - otros[0]) < 0.005:
    st.warning("Los R² son muy parecidos entre modelos; con estos datos la elección del orden es poco concluyente.")

unidad_k = unidades_m[mejor]
a0_ref = c[0] if abs(t[0]) < 1e-12 else a["a0"]
tiempos = {n: tiempo(mejor, a["k"], a0_ref, r) for n, r in REMANENTE.items()}

st.subheader("Constante cinética (kₐ)")
if mejor in (0, 1):
    st.latex(rf"m = -k_a \;\;\Rightarrow\;\; k_a = -m = {-a['pendiente']:.5g}")
else:
    st.latex(rf"m = k_a \;\;\Rightarrow\;\; k_a = m = {a['pendiente']:.5g}")
st.metric(f"Constante cinética kₐ ({unidad_k})", f"{a['k']:.5g}")

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

cols = st.columns(4)
for col, n in zip(cols, ("t50", "t90", "t95", "t98")):
    with col:
        st.markdown(f"**{NOMBRES[n]}**")
        st.latex(ECUACIONES[mejor][n])
        st.metric(f"Valor ({unidad_t})", f"{tiempos[n]:.4g}")
# =====================================================
# 5. MÓDULO ARRHENIUS
# =====================================================
R_GAS = 8.314  # J/(mol·K)
AZUL, NARANJA, MORADO, ROJO = "#1F77B4", "#FF7F0E", "#9467BD", "#D62728"


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


def estilo_ejes(fig, titulo, xt, yt, x_range=None, y_range=None):
    """Mismo estilo de los gráficos de orden de reacción: ejes negros, sin cuadrícula ni leyenda."""
    eje = dict(showgrid=False, zeroline=False, showline=True,
               linecolor="black", linewidth=2, ticks="outside")
    fig.update_layout(
        font=dict(family="Computer Modern Serif, serif", size=14),
        title=titulo, xaxis_title=xt, yaxis_title=yt,
        height=380, margin=dict(t=80, b=40), showlegend=False, plot_bgcolor="white",
        xaxis=dict(range=x_range, **eje), yaxis=dict(range=y_range, **eje))
    return fig


st.header("5. Módulo Arrhenius")
st.write("Ecuación de Arrhenius:")
st.latex(r"k = A\,e^{-E_a/RT}")
st.write("Forma linealizada (recta y = mx + b):")
st.latex(r"\ln k = -\dfrac{E_a}{R}\times\dfrac{1}{T} + \ln A \qquad\qquad m = -\dfrac{E_a}{R}")
st.write("Ingresa las constantes k obtenidas a diferentes temperaturas "
         "(todas del mismo orden de reacción y con las mismas unidades).")

ca1, ca2 = st.columns(2)
with ca1:
    unidad_T = st.radio("Unidad de temperatura", ["°C", "K"], horizontal=True)
    archivo_arr = st.file_uploader(
        "…o sube un CSV/Excel (col. 1 = temperatura, col. 2 = k)",
        type=["csv", "xlsx"], key="archivo_arr",
        help="La primera fila debe ser el encabezado (por ejemplo: Temperatura, k).")
arr_base = pd.DataFrame({
    "Temperatura": [40.0, 50.0, 60.0, 70.0],
    "k": [0.0021, 0.0058, 0.0148, 0.0360],
})
nombre_arr = ""
if archivo_arr is not None:
    try:
        arr_base = leer_archivo_arr(archivo_arr)
        nombre_arr = archivo_arr.name
        ca1.success(f"Archivo cargado: {archivo_arr.name} ({len(arr_base)} filas)")
    except Exception as e:
        ca1.error(f"No pude leer el archivo ({e}). Se muestra la tabla de ejemplo.")
with ca2:
    arr = st.data_editor(arr_base, num_rows="dynamic", use_container_width=True,
                         key=f"arrhenius_{nombre_arr}")

arr = arr.dropna()
if len(arr) < 3:
    st.warning("Ingresa al menos 3 pares (temperatura, k) para el análisis de Arrhenius.")
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

# --- Gráfico 1: k vs T (azul) ---
pad_T = (T_user.max() - T_user.min()) * 0.08 or 1
T_c = np.linspace(T_user.min(), T_user.max(), 100)
k_c = A_pre * np.exp(-Ea / (R_GAS * (T_c + offset)))
fig_k = go.Figure()
fig_k.add_trace(go.Scatter(x=T_user, y=k_arr, mode="markers", marker=dict(size=10, color=AZUL)))
fig_k.add_trace(go.Scatter(x=T_c, y=k_c, mode="lines", line=dict(color=AZUL)))
estilo_ejes(fig_k, "k vs T<br><sup>k = A·e^(−Ea/RT)</sup>", f"Temperatura ({unidad_T})", "k",
            [T_user.min() - pad_T, T_user.max() + pad_T], [0, k_arr.max() * 1.12])

# --- Gráfico 2: ln k vs 1/T (naranja) ---
signo = "+" if reg_arr.intercept >= 0 else "-"
ecuacion = f"y = {reg_arr.slope:.5g}x {signo} {abs(reg_arr.intercept):.5g}"
pad_x = (inv_T.max() - inv_T.min()) * 0.08 or 1e-5
pad_y = (ln_k.max() - ln_k.min()) * 0.12 or 1
x_l = np.linspace(inv_T.min(), inv_T.max(), 100)
fig_lin = go.Figure()
fig_lin.add_trace(go.Scatter(x=inv_T, y=ln_k, mode="markers", marker=dict(size=10, color=NARANJA)))
fig_lin.add_trace(go.Scatter(x=x_l, y=reg_arr.slope * x_l + reg_arr.intercept,
                             mode="lines", line=dict(color=NARANJA)))
estilo_ejes(fig_lin, f"ln k vs 1/T<br><sup>{ecuacion} | R² = {r2_arr:.4f}</sup>",
            "1/T (K⁻¹)", "ln k",
            [inv_T.min() - pad_x, inv_T.max() + pad_x], [ln_k.min() - pad_y, ln_k.max() + pad_y])
fig_lin.update_xaxes(tickformat=".2e")

gk, gl = st.columns(2)
with gk:
    st.plotly_chart(fig_k, use_container_width=True)
with gl:
    st.plotly_chart(fig_lin, use_container_width=True)

# --- Pendiente, Ea y A ---
st.latex(rf"m = -\dfrac{{E_a}}{{R}} = {reg_arr.slope:.5g}\ \text{{K}}"
         rf"\;\;\Rightarrow\;\; E_a = -m\,R = {Ea/1000:.2f}\ \text{{kJ/mol}}")

tabla_arr = pd.DataFrame({
    "T (K)": T_K, "1/T (1/K)": inv_T, "k": k_arr, "ln k": ln_k,
})
st.dataframe(tabla_arr.style.format({"T (K)": "{:.2f}", "1/T (1/K)": "{:.6e}",
                                     "k": "{:.5g}", "ln k": "{:.4f}"}),
             use_container_width=True, hide_index=True)

ar1, ar2, ar3, ar4, ar5 = st.columns(5)
ar1.metric("Ea (kJ/mol)", f"{Ea/1000:.2f}")
ar2.metric("Ea (kcal/mol)", f"{Ea/4184:.2f}")
ar3.metric("ln A (intercepto)", f"{reg_arr.intercept:.4f}")
ar4.metric("Factor preexponencial A", f"{A_pre:.4e}")
ar5.metric("R² Arrhenius", f"{r2_arr:.4f}")
st.caption("A tiene las mismas unidades de k.")
if r2_arr < 0.95:
    st.warning("El R² de Arrhenius es bajo; la predicción puede no ser confiable.")

# =====================================================
# 6. PREDICCIÓN DE ESTABILIDAD
# =====================================================
st.header("6. Predicción de estabilidad")

orden_pred = st.selectbox(
    "Orden de reacción para la predicción",
    [0, 1, 2], index=mejor,
    format_func=lambda o: ORDENES[o]["nombre"] + (" (detectado en la sección 4)" if o == mejor else ""),
    key=f"orden_pred_{mejor}",
    help="Por defecto es el orden detectado. Puedes cambiarlo si quieres comparar.")
if orden_pred != mejor:
    st.warning(f"Estás usando {ORDENES[orden_pred]['nombre'].lower()} y no el detectado "
               f"({ORDENES[mejor]['nombre'].lower()}). Las k de la sección 5 deben corresponder a ese orden.")

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
    st.error("Escribe las temperaturas solo con números separados por comas.")
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
st.dataframe(vista.style.format("{:.4g}"), use_container_width=True, hide_index=True)
st.caption("La primera fila es la temperatura de referencia.")

T_min_exp, T_max_exp = T_K.min() - offset, T_K.max() - offset
fuera = [x for x in todas if x < T_min_exp or x > T_max_exp]
if fuera:
    st.warning(f"Extrapolación: {fuera} está fuera del rango experimental "
               f"({T_min_exp:.1f} a {T_max_exp:.1f} {unidad_T}). La predicción es menos confiable.")
# =====================================================
# 7. CONCLUSIONES AUTOMÁTICAS
# =====================================================
st.header("7. Conclusiones automáticas")

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
        L.append("⚠️ La diferencia entre modelos es muy pequeña; se recomienda más puntos "
                 "experimentales o una mayor conversión para confirmar el orden.")
    if len(t) < 5:
        L.append("⚠️ Se usaron pocos puntos (menos de 5), lo que reduce la confiabilidad del ajuste.")
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
        L.append("⚠️ El R² de Arrhenius es bajo: el mecanismo podría cambiar con la temperatura "
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
        L.append(f"⚠️ Algunas temperaturas ({fuera}) están fuera del rango experimental "
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
    """Una llamada corta a Gemini (sin búsqueda web). El mismo prompt reutiliza la respuesta guardada."""
    import time
    from google import genai
    from google.genai import types
    cliente = genai.Client(api_key=clave, http_options=types.HttpOptions(timeout=60_000))
    rapido = True
    for _ in range(3):
        kw = dict(temperature=0.2, max_output_tokens=700)
        if rapido:
            kw["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
        try:
            resp = cliente.models.generate_content(
                model=modelo, contents=prompt, config=types.GenerateContentConfig(**kw))
            return resp.text
        except Exception as e:
            msg = str(e).lower()
            if rapido and "thinking" in msg:
                rapido = False
                continue
            if any(x in msg for x in ("503", "unavailable", "disconnected", "timed out", "timeout", "ssl")):
                time.sleep(3)
                continue
            raise
    raise RuntimeError("El modelo no respondió. Intenta de nuevo en un momento.")


st.subheader("Conclusión con IA (Gemini)")
clave = st.text_input("Clave de API de Gemini", type="password",
                      help="Se obtiene gratis en aistudio.google.com/apikey. No se guarda.")
farmaco = st.text_input("Nombre del fármaco o producto (opcional)", "")
modelo = st.text_input("Modelo de Gemini", "gemini-3.8-flash",
                       help="Si da error 404, cambia el nombre por uno vigente en aistudio.google.com")

if st.button("Generar conclusión con IA"):
    if not clave:
        st.error("Escribe tu clave de API para usar la IA.")
    else:
        prompt = f"""Eres experto en fisicoquímica farmacéutica. Redacta en español una conclusión breve y técnica
(2 a 3 párrafos cortos, máximo 180 palabras) para un informe universitario, usando SOLO estos datos:

Fármaco: {farmaco or 'no especificado'}
Orden de reacción: {ORDENES[mejor]['nombre']} (R² = {a['r2']:.4f}); k = {a['k']:.4g} {unidad_k}
t1/2 = {tiempos['t50']:.4g} {unidad_t}; t90 = {tiempos['t90']:.4g} {unidad_t}; t95 = {tiempos['t95']:.4g} {unidad_t}; t98 = {tiempos['t98']:.4g} {unidad_t}
Arrhenius: Ea = {Ea/1000:.1f} kJ/mol, R² = {r2_arr:.4f}, Q10 = {Q10:.2f}
A {T_ref:g} {unidad_T}: t90 = {t90_ref:.4g} {unidad_t}
Extrapolación fuera del rango experimental: {'sí' if fuera else 'no'}

Incluye: orden y calidad del ajuste, sensibilidad a la temperatura (Ea), implicación para el almacenamiento
y una limitación. No inventes valores, mecanismos ni referencias."""
        try:
            with st.spinner("Generando conclusión..."):
                st.session_state["texto_ia"] = generar_ia(clave, modelo, prompt)
        except Exception as e:
            st.error(f"No se pudo usar la IA ({e}). Usa la conclusión por reglas de arriba.")

if "texto_ia" in st.session_state:
    st.markdown(st.session_state["texto_ia"])

# ---- Descarga ----
informe = "CONCLUSIÓN POR REGLAS\n\n" + texto_reglas.replace("**", "").replace("*", "")
if "texto_ia" in st.session_state:
    informe += "\n\nCONCLUSIÓN CON IA\n\n" + st.session_state["texto_ia"]
st.download_button("Descargar conclusiones (.txt)", informe, file_name="conclusiones_estabilidad.txt")