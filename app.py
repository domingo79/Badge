"""
Conteggio Ore & Stima Stipendio - App Streamlit
"""

import streamlit as st
import pandas as pd
from datetime import date
import os

CSV_PATH = "turni.csv"
SOGLIA_MENSILE_ORE = 172  # soglia CCNL

# Valore di riferimento indicativo (6° livello CCNL Turismo/Pubblici Esercizi, minimo tabellare mensile / 172h).
# PAGA BASE:       937.80
# CONDINGENZA:     520.51
# AUMENTO dal 6/26  33.25
# TOTALE          1491.27
# RATEO 13^ 14^  = 124,2725
PAGA_ORARIA_DEFAULT = 8.67


def carica_turni() -> pd.DataFrame:
    if os.path.exists(CSV_PATH):
        df = pd.read_csv(CSV_PATH, dtype={"data": str, "etichetta": str})
        df["ore"] = pd.to_numeric(df["ore"], errors="coerce").fillna(0.0)
    else:
        df = pd.DataFrame(columns=["data", "etichetta", "ore"])
    return df


def salva_turni(df: pd.DataFrame) -> None:
    df.to_csv(CSV_PATH, index=False)


st.set_page_config(page_title="Conteggio Ore",
                   page_icon="🕒", layout="centered")
st.title("🕒 Conteggio Ore & Stipendio")

df = carica_turni()
oggi = date.today()
oggi_str = oggi.isoformat()

# --- Inserimento nuovo turno ---
st.subheader("➕ Aggiungi turno")
with st.form("nuovo_turno", clear_on_submit=True):
    c1, c2, c3 = st.columns([2, 2, 1.5])
    data_input = c1.date_input("Data", value=oggi)
    etichetta_input = c2.selectbox(
        "Turno", ["Mattina", "Pranzo", "Cena", "Altro"])
    ore_input = c3.number_input(
        "Ore", min_value=0.0, max_value=14.0, step=0.5, value=2.0)
    submitted = st.form_submit_button(
        "Salva turno", use_container_width=True, type="primary")
    if submitted:
        nuova_riga = pd.DataFrame([{
            "data": data_input.isoformat(),
            "etichetta": etichetta_input,
            "ore": ore_input,
        }])
        df = pd.concat([df, nuova_riga], ignore_index=True)
        salva_turni(df)
        st.success(f"Turno {etichetta_input} da {ore_input}h salvato.")
        st.rerun()

st.divider()

# --- Turni di oggi ---
st.subheader("📅 Turni di oggi")
turni_oggi = df[df["data"] == oggi_str].copy()
if turni_oggi.empty:
    st.write("Nessun turno registrato oggi.")
else:
    for i, row in turni_oggi.iterrows():
        c1, c2, c3 = st.columns([2, 2, 1])
        c1.write(row["etichetta"])
        c2.write(f"{row['ore']:.2f} h")
        if c3.button("🗑️", key=f"del_{i}"):
            df = df.drop(index=i)
            salva_turni(df)
            st.rerun()
    st.write(f"**Totale oggi: {turni_oggi['ore'].sum():.2f} ore**")

st.divider()

# --- Riepilogo mensile e stima stipendio ---
st.subheader("📊 Riepilogo mensile")

paga_oraria = st.number_input(
    "Paga oraria lorda (€) — controlla la voce 'minimo tabellare' sulla tua busta paga",
    min_value=0.0, value=PAGA_ORARIA_DEFAULT, step=0.01, format="%.2f"
)

if not df.empty:
    df["mese"] = df["data"].str[:7]  # YYYY-MM
    mesi_disponibili = sorted(df["mese"].unique(), reverse=True)
    mese_scelto = st.selectbox("Seleziona mese", mesi_disponibili)

    df_mese = df[df["mese"] == mese_scelto]
    totale_ore = df_mese["ore"].sum()
    stima_lordo = totale_ore * paga_oraria

    m1, m2 = st.columns(2)
    m1.metric("Totale ore del mese", f"{totale_ore:.2f} h")
    m2.metric("Stima lordo mensile", f"{stima_lordo:.2f} €")

    delta = totale_ore - SOGLIA_MENSILE_ORE
    if delta >= 0:
        st.success(
            f"Hai superato la soglia di {SOGLIA_MENSILE_ORE}h di {delta:.2f} ore")
    else:
        st.warning(
            f"Mancano {abs(delta):.2f} ore per raggiungere la soglia di {SOGLIA_MENSILE_ORE}h")

    st.caption(
        "⚠️ Stima indicativa: non considera straordinari, festività, "
        "scatti di anzianità o altre voci in busta paga. Verifica sempre "
        "con la tua busta paga reale o con il consulente del lavoro."
    )

    with st.expander("Dettaglio turni del mese, raggruppati per giorno"):
        riepilogo_giorni = df_mese.groupby("data")["ore"].sum().reset_index()
        riepilogo_giorni.columns = ["Data", "Ore totali"]
        st.dataframe(riepilogo_giorni.sort_values("Data"),
                     use_container_width=True, hide_index=True)

    with st.expander("✏️ Dettaglio e correzione turni del mese"):
        st.caption(
            "Tabella modificabile: correggi data, turno o ore direttamente qui, poi salva.")
        tabella_edit = df_mese[["data", "etichetta",
                                "ore"]].sort_values("data").copy()
        edit_mese = st.data_editor(
            tabella_edit,
            use_container_width=True,
            hide_index=True,
            num_rows="dynamic",
            key=f"editor_mese_{mese_scelto}",
            column_config={
                "data": st.column_config.TextColumn("Data (AAAA-MM-GG)", required=True),
                "etichetta": st.column_config.SelectboxColumn(
                    "Turno", options=["Mattina", "Pranzo", "Cena", "Altro"], required=True
                ),
                "ore": st.column_config.NumberColumn(
                    "Ore", min_value=0.0, max_value=14.0, step=0.5, format="%.2f", required=True
                ),
            },
        )
        if st.button("💾 Salva modifiche del mese", use_container_width=True):
            df_base = df.drop(index=tabella_edit.index).drop(
                columns=["mese"], errors="ignore")
            edit_mese = edit_mese.copy()
            df_base = pd.concat(
                [df_base, edit_mese[["data", "etichetta", "ore"]]], ignore_index=True)
            salva_turni(df_base)
            st.success("Modifiche salvate.")
            st.rerun()
else:
    st.write("Nessun dato ancora registrato.")
