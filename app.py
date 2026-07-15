"""
Conteggio Ore & Stima Stipendio - App Streamlit
Con gestione maggiorazioni: domenicale, notturno, festivo, formazione
"""

import streamlit as st
import pandas as pd
from datetime import date
import os

CSV_PATH = "turni.csv"
SOGLIA_MENSILE_ORE = 172  # soglia CCNL

# Valore di riferimento indicativo (6° livello CCNL Turismo/Pubblici Esercizi, minimo tabellare mensile / 172h).
# PAGA BASE:       937.80
# CONTINGENZA:     520.51
# AUMENTO dal 6/26  33.26
# TOTALE          1491.27
RETRIBUZIONE_MENSILE_DEFAULT = 1491.27
PAGA_ORARIA_DEFAULT = RETRIBUZIONE_MENSILE_DEFAULT / SOGLIA_MENSILE_ORE

# Moltiplicatori di default per le maggiorazioni.
# NB: "Festivo" è una stima indicativa (+30%), verificala sul tuo CCNL/busta paga.
MOLTIPLICATORI_DEFAULT = {
    "domenicale": 0.10,   # +10%
    "notturno": 0.60,     # +60% (8.67*1.60 = 13.87)
    "festivo": 0.30,      # +30% (indicativo, da verificare)
}

COLONNE = ["data", "etichetta", "ore", "domenicale",
           "notturno", "festivo", "formazione"]


def carica_turni() -> pd.DataFrame:
    if os.path.exists(CSV_PATH):
        df = pd.read_csv(CSV_PATH, dtype={"data": str, "etichetta": str})
        df["ore"] = pd.to_numeric(df["ore"], errors="coerce").fillna(0.0)
        for col in ["domenicale", "notturno", "festivo", "formazione"]:
            if col not in df.columns:
                df[col] = False
            df[col] = df[col].fillna(False).astype(bool)
        df = df[COLONNE]
    else:
        df = pd.DataFrame(columns=COLONNE)
    return df


def salva_turni(df: pd.DataFrame) -> None:
    df.to_csv(CSV_PATH, index=False)


def calcola_moltiplicatore(row, mult: dict) -> float:
    """Formazione esclude le altre maggiorazioni. Le altre sono cumulabili."""
    if row.get("formazione", False):
        return 1.0
    m = 1.0
    if row.get("domenicale", False):
        m += mult["domenicale"]
    if row.get("notturno", False):
        m += mult["notturno"]
    if row.get("festivo", False):
        m += mult["festivo"]
    return m


def etichetta_maggiorazioni(row) -> str:
    if row.get("formazione", False):
        return "Formazione"
    tag = []
    if row.get("domenicale", False):
        tag.append("Domenicale")
    if row.get("notturno", False):
        tag.append("Notturno")
    if row.get("festivo", False):
        tag.append("Festivo")
    return " + ".join(tag) if tag else "Normale"


st.set_page_config(page_title="Conteggio Ore",
                   page_icon="🕒", layout="centered")
st.title("🕒 Conteggio Ore & Stipendio")

df = carica_turni()
oggi = date.today()
oggi_str = oggi.isoformat()

# --- Impostazioni paga (sidebar) ---
with st.sidebar:
    st.header("⚙️ Impostazioni paga")
    paga_oraria = st.number_input(
        "Paga oraria base (€) — 'minimo tabellare' / 172h dalla busta paga",
        min_value=0.0, value=PAGA_ORARIA_DEFAULT, step=0.01, format="%.2f"
    )
    retribuzione_mensile = st.number_input(
        "Retribuzione mensile teorica (€) — per calcolo ratei 13ª/14ª",
        min_value=0.0, value=RETRIBUZIONE_MENSILE_DEFAULT, step=0.01, format="%.2f"
    )
    st.caption("Maggiorazioni (in % sulla paga base, cumulabili)")
    perc_domenicale = st.number_input(
        "Domenicale %", min_value=0.0, value=MOLTIPLICATORI_DEFAULT["domenicale"] * 100, step=1.0) / 100
    perc_notturno = st.number_input(
        "Notturno %", min_value=0.0, value=MOLTIPLICATORI_DEFAULT["notturno"] * 100, step=1.0) / 100
    perc_festivo = st.number_input("Festivo % (indicativo, verifica CCNL)",
                                   min_value=0.0, value=MOLTIPLICATORI_DEFAULT["festivo"] * 100, step=1.0) / 100
    MOLTIPLICATORI = {"domenicale": perc_domenicale,
                      "notturno": perc_notturno, "festivo": perc_festivo}

# --- Inserimento nuovo turno ---
st.subheader("➕ Aggiungi turno")
with st.form("nuovo_turno", clear_on_submit=True):
    c1, c2, c3 = st.columns([2, 2, 1.5])
    data_input = c1.date_input("Data", value=oggi)
    etichetta_input = c2.selectbox(
        "Turno", ["Mattina", "Pranzo", "Cena", "Altro"])
    ore_input = c3.number_input(
        "Ore", min_value=0.0, max_value=14.0, step=0.5, value=2.0)

    st.write("Maggiorazioni applicabili a questo turno:")
    m1, m2, m3, m4 = st.columns(4)
    dom_input = m1.checkbox("Domenicale")
    nott_input = m2.checkbox("Notturno")
    fest_input = m3.checkbox("Festivo")
    form_input = m4.checkbox("Formazione")

    submitted = st.form_submit_button(
        "Salva turno", use_container_width=True, type="primary")
    if submitted:
        nuova_riga = pd.DataFrame([{
            "data": data_input.isoformat(),
            "etichetta": etichetta_input,
            "ore": ore_input,
            "domenicale": dom_input,
            "notturno": nott_input,
            "festivo": fest_input,
            "formazione": form_input,
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
        c1, c2, c3, c4 = st.columns([2, 1.5, 2, 1])
        c1.write(row["etichetta"])
        c2.write(f"{row['ore']:.2f} h")
        c3.write(etichetta_maggiorazioni(row))
        if c4.button("🗑️", key=f"del_{i}"):
            df = df.drop(index=i)
            salva_turni(df)
            st.rerun()
    st.write(f"**Totale oggi: {turni_oggi['ore'].sum():.2f} ore**")

st.divider()

# --- Riepilogo mensile e stima stipendio ---
st.subheader("📊 Riepilogo mensile")

if not df.empty:
    df["mese"] = df["data"].str[:7]  # YYYY-MM
    mesi_disponibili = sorted(df["mese"].unique(), reverse=True)
    mese_scelto = st.selectbox("Seleziona mese", mesi_disponibili)

    df_mese = df[df["mese"] == mese_scelto].copy()
    df_mese["moltiplicatore"] = df_mese.apply(
        lambda r: calcola_moltiplicatore(r, MOLTIPLICATORI), axis=1)
    df_mese["importo"] = df_mese["ore"] * \
        paga_oraria * df_mese["moltiplicatore"]
    df_mese["categoria"] = df_mese.apply(etichetta_maggiorazioni, axis=1)

    totale_ore = df_mese["ore"].sum()
    stima_lordo = df_mese["importo"].sum()

    m1, m2 = st.columns(2)
    m1.metric("Totale ore del mese", f"{totale_ore:.2f} h")
    m2.metric("Stima lordo mensile (con maggiorazioni)",
              f"{stima_lordo:.2f} €")

    delta = totale_ore - SOGLIA_MENSILE_ORE
    if delta >= 0:
        st.success(
            f"Hai superato la soglia di {SOGLIA_MENSILE_ORE}h di {delta:.2f} ore")
    else:
        st.warning(
            f"Mancano {abs(delta):.2f} ore per raggiungere la soglia di {SOGLIA_MENSILE_ORE}h")

    # --- Ratei 13ª e 14ª ---
    st.subheader("🎁 Ratei 13ª e 14ª")
    rateo_mensile_pieno = retribuzione_mensile / 12
    proporzione = min(totale_ore / SOGLIA_MENSILE_ORE,
                      1.0) if SOGLIA_MENSILE_ORE else 0
    rateo_tredicesima = rateo_mensile_pieno * proporzione
    rateo_quattordicesima = rateo_mensile_pieno * proporzione

    r1, r2 = st.columns(2)
    r1.metric("Rateo 13ª maturato", f"{rateo_tredicesima:.2f} €")
    r2.metric("Rateo 14ª maturato", f"{rateo_quattordicesima:.2f} €")

    st.caption(
        f"Calcolo: ({retribuzione_mensile:.2f} € / 12) × ({totale_ore:.2f}h / {SOGLIA_MENSILE_ORE}h) = "
        f"{rateo_mensile_pieno:.4f} € × {proporzione:.4f}"
    )

    totale_complessivo = stima_lordo + rateo_tredicesima + rateo_quattordicesima
    st.metric("💰 Stima totale (lordo + ratei 13ª/14ª)",
              f"{totale_complessivo:.2f} €")

    st.caption(
        "⚠️ Stima indicativa: non considera contributi, IRPEF, scatti di anzianità, "
        "TFR o altre voci in busta paga. Verifica sempre con la busta paga reale o "
        "con il consulente del lavoro. La maggiorazione festiva è un valore stimato: "
        "controllala sul tuo CCNL."
    )

    with st.expander("Dettaglio turni del mese, raggruppati per giorno"):
        riepilogo_giorni = df_mese.groupby("data").agg(
            ore_totali=("ore", "sum"), importo_totale=("importo", "sum")
        ).reset_index()
        riepilogo_giorni.columns = ["Data", "Ore totali", "Importo (€)"]
        st.dataframe(riepilogo_giorni.sort_values("Data"),
                     use_container_width=True, hide_index=True)

    with st.expander("📈 Riepilogo per categoria (normale/domenicale/notturno/festivo/formazione)"):
        riepilogo_categoria = df_mese.groupby("categoria").agg(
            ore=("ore", "sum"), importo=("importo", "sum")
        ).reset_index()
        riepilogo_categoria.columns = ["Categoria", "Ore", "Importo (€)"]
        st.dataframe(riepilogo_categoria,
                     use_container_width=True, hide_index=True)

    with st.expander("✏️ Dettaglio e correzione turni del mese"):
        st.caption(
            "Tabella modificabile: correggi data, turno, ore o maggiorazioni, poi salva.")
        tabella_edit = df_mese[COLONNE].sort_values("data").copy()
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
                "domenicale": st.column_config.CheckboxColumn("Domenicale"),
                "notturno": st.column_config.CheckboxColumn("Notturno"),
                "festivo": st.column_config.CheckboxColumn("Festivo"),
                "formazione": st.column_config.CheckboxColumn("Formazione"),
            },
        )
        if st.button("💾 Salva modifiche del mese", use_container_width=True):
            df_base = df.drop(index=tabella_edit.index).drop(
                columns=["mese"], errors="ignore")
            edit_mese = edit_mese.copy()
            df_base = pd.concat(
                [df_base, edit_mese[COLONNE]], ignore_index=True)
            salva_turni(df_base)
            st.success("Modifiche salvate.")
            st.rerun()
else:
    st.write("Nessun dato ancora registrato.")
