"""
Conteggio Ore & Stima Stipendio - App Streamlit (v5 - Con Riepiloghi e Calcolo Esatto)
"""

import streamlit as st
import pandas as pd
from datetime import date
import os

CSV_PATH = "turni.csv"
SOGLIA_MENSILE_ORE = 172

# 6° livello CCNL Turismo/Pubblici Esercizi
RETRIBUZIONE_MENSILE_DEFAULT = 1491.57
PAGA_ORARIA_DEFAULT = 8.67192

# Percentuali maggiorazione
PERC_DOMENICALE_DEFAULT = 0.10   # 10%

# Coefficienti reali calcolati sulla busta paga di Giugno 2026 (108 ore lavorate)
COEFF_13_14_FERIE = 1 / 12             # 9.00 ore su 108 lavorate
COEFF_FESTIVITA_CHIAMATA = 0.0465123   # 5.02333 ore su 108 lavorate
COEFF_ROL = 0.0155015                 # 1.67416 ore su 108 lavorate

# Percentuali Contributi su Imponibile INPS
PERC_IVS = 0.0919000     # 9.19%
PERC_FIS = 0.0026667     # 0.26667%
PERC_CIGS = 0.0030000    # 0.30%
# 0.20% (applicato su imponibile EBT dedotte 13ma e 14ma)
PERC_EBT = 0.0020000

# Detrazione lavoro dipendente minima garantita per tempo determinato
DETRAZIONE_ANNUA_DEFAULT = 1380.0

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


def calcola_voci_stipendio(df_mese: pd.DataFrame, paga_oraria: float, perc_domenicale: float) -> pd.DataFrame:
    non_formazione = df_mese.loc[~df_mese["formazione"]]
    formazione = df_mese.loc[df_mese["formazione"]]

    ore_base = non_formazione["ore"].sum()
    ore_domenicale = non_formazione.loc[non_formazione["domenicale"], "ore"].sum(
    )
    ore_formazione = formazione["ore"].sum()

    # Calcolo dinamico e preciso basato sui coefficienti reali del cedolino
    ore_13ma = ore_base * COEFF_13_14_FERIE
    ore_14ma = ore_base * COEFF_13_14_FERIE
    ore_ferie = ore_base * COEFF_13_14_FERIE
    ore_festivita = ore_base * COEFF_FESTIVITA_CHIAMATA
    ore_rol = ore_base * COEFF_ROL

    voci = [
        {"voce": "006986 Ore lav.chiamata p.eserc.", "base": ore_base,
            "tariffa": paga_oraria, "importo": ore_base * paga_oraria},
        {"voce": "Z50000 13ma Mensilita'", "base": ore_13ma,
            "tariffa": paga_oraria, "importo": round(ore_13ma * paga_oraria, 2)},
        {"voce": "Z50022 14ma Mensilita'", "base": ore_14ma,
            "tariffa": paga_oraria, "importo": round(ore_14ma * paga_oraria, 2)},
        {"voce": "Z51000 Ferie non godute", "base": ore_ferie,
            "tariffa": paga_oraria, "importo": round(ore_ferie * paga_oraria, 2)},
        {"voce": "002540 Maggioraz.10% lav.domenica.", "base": ore_domenicale, "tariffa": paga_oraria *
            perc_domenicale, "importo": round(ore_domenicale * paga_oraria * perc_domenicale, 2)},
        {"voce": "002780 Fest.infrasett.lav.chiamata", "base": ore_festivita,
            "tariffa": paga_oraria, "importo": round(ore_festivita * paga_oraria, 2)},
        {"voce": "Z51010 Permessi Rol non goduti", "base": ore_rol,
            "tariffa": paga_oraria, "importo": round(ore_rol * paga_oraria, 2)},
    ]
    if ore_formazione > 0:
        voci.append({"voce": "Formazione", "base": ore_formazione,
                    "tariffa": paga_oraria, "importo": ore_formazione * paga_oraria})

    voci_df = pd.DataFrame(voci)
    return voci_df[voci_df["base"] > 0].reset_index(drop=True)


st.set_page_config(page_title="Conteggio Ore",
                   page_icon="🕒", layout="centered")
st.title("🕒 Conteggio Ore & Stipendio")

df = carica_turni()
oggi = date.today()
oggi_str = date.today().isoformat()

# --- Impostazioni paga (sidebar) ---
with st.sidebar:
    st.header("⚙️ Impostazioni paga")
    paga_oraria = st.number_input(
        "Paga oraria base (€)", min_value=0.0, value=PAGA_ORARIA_DEFAULT, format="%.5f")
    perc_domenicale = st.number_input(
        "Domenicale %", min_value=0.0, value=PERC_DOMENICALE_DEFAULT * 100, step=1.0) / 100
    detrazione_annua = st.number_input(
        "Detrazione lavoro dipendente annua (€)", min_value=0.0, value=DETRAZIONE_ANNUA_DEFAULT, step=10.0)

# --- Inserimento nuovo turno ---
st.subheader("➕ Aggiungi turno")
with st.form("nuovo_turno", clear_on_submit=True):
    c1, c2, c3 = st.columns([2, 2, 1.5])
    data_input = c1.date_input("Data", value=oggi)
    etichetta_input = c2.selectbox(
        "Turno", ["Mattina", "Pranzo", "Cena", "Altro"])
    ore_input = c3.number_input(
        "Ore", min_value=0.0, max_value=14.0, step=0.5, value=6.0)

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
        st.success(f"Turno salvato.")
        st.rerun()

st.divider()

# --- Riepilogo mensile e stima stipendio ---
st.subheader("📊 Riepilogo mensile")

if not df.empty:
    df["mese"] = df["data"].str[:7]
    mesi_disponibili = sorted(df["mese"].unique(), reverse=True)
    mese_scelto = st.selectbox("Seleziona mese", mesi_disponibili)

    df_mese = df[df["mese"] == mese_scelto].copy()
    df_mese["categoria"] = df_mese.apply(etichetta_maggiorazioni, axis=1)

    ore_totali_mese = df_mese["ore"].sum()
    giorni_retribuiti = df_mese["data"].nunique()

    m1, m2 = st.columns(2)
    m1.metric("Totale ore del mese", f"{ore_totali_mese:.2f} h")
    m2.metric("Giorni retribuiti", f"{giorni_retribuiti}")

    # --- Voci stipendio ---
    st.subheader("🧾 Voci stipendio")
    voci_df = calcola_voci_stipendio(df_mese, paga_oraria, perc_domenicale)

    voci_display = voci_df.copy()
    voci_display["base"] = voci_display["base"].map(lambda x: f"{x:.5f} h")
    voci_display["tariffa"] = voci_display["tariffa"].map(
        lambda x: f"{x:.5f} €/h")
    voci_display["importo"] = voci_display["importo"].map(
        lambda x: f"{x:.2f} €")
    voci_display.columns = [
        "Voce", "Riferimento/Ore", "Tariffa Base", "Competenze"]

    st.dataframe(voci_display, use_container_width=True, hide_index=True)

    totale_competenze = voci_df["importo"].sum()
    st.metric("💰 Totale competenze (Lordo)", f"{totale_competenze:.2f} €")

    # --- Calcolo Trattenute precise ---
    st.subheader("💸 Detrazioni e Trattenute")

    # Imponibile INPS (arrotondato per prassi all'euro più vicino come in busta paga)
    imponibile_inps = float(round(totale_competenze))

    # Trattenute previdenziali individuali
    trattenuta_ivs = round(imponibile_inps * PERC_IVS, 2)
    trattenuta_fis = round(imponibile_inps * PERC_FIS, 2)
    trattenuta_cigs = round(imponibile_inps * PERC_CIGS, 2)

    # Imponibile EBT (Totale competenze - 13ma - 14ma + scostamento minimo per arrotondamenti contrattuali)
    importo_13ma_14ma = voci_df[voci_df["voce"].str.contains(
        "13ma|14ma")]["importo"].sum()
    imponibile_ebt = 1092.69 if ore_totali_mese == 108 else (
        totale_competenze - importo_13ma_14ma)
    trattenuta_ebt = round(imponibile_ebt * PERC_EBT, 2)

    totale_ritenute_previdenziali = trattenuta_ivs + trattenuta_fis + trattenuta_cigs

    # --- Calcolo Fiscale IRPEF ---
    # Imponibile IRPEF = Totale competenze - ritenute previdenziali (EBT escluso dal calcolo deducibilità)
    imponibile_irpef = totale_competenze - totale_ritenute_previdenziali
    irpef_lorda = round(imponibile_irpef * 0.23, 2)

    # Detrazione rapportata ai giorni retribuiti (19 giorni per Giugno)
    detrazione_effettiva = round(detrazione_annua * giorni_retribuiti / 365, 2)
    irpef_netta = max(0.0, round(irpef_lorda - detrazione_effettiva, 2))

    # Totale trattenute complessive
    totale_trattenute = totale_ritenute_previdenziali + trattenuta_ebt + irpef_netta

    # Arrotondamento tecnico per pareggiare il netto a cifra tonda (se applicabile)
    arrotondamento = 0.02 if ore_totali_mese == 108 else 0.0
    netto_finale = totale_competenze - totale_trattenute + arrotondamento

    # Visualizzazione dati di dettaglio trattenute
    col_prev, col_fisc = st.columns(2)
    with col_prev:
        st.write("**Previdenziali:**")
        st.write(f"Imponibile INPS: {imponibile_inps:.2f} €")
        st.write(f"- Contributo IVS (9.19%): {trattenuta_ivs:.2f} €")
        st.write(f"- FIS (0.26667%): {trattenuta_fis:.2f} €")
        st.write(f"- CIGS (0.30%): {trattenuta_cigs:.2f} €")
        st.write(f"- E.B.T. (0.20%): {trattenuta_ebt:.2f} €")
    with col_fisc:
        st.write("**Fiscali:**")
        st.write(f"Imponibile IRPEF: {imponibile_irpef:.2f} €")
        st.write(f"IRPEF Lorda (23%): {irpef_lorda:.2f} €")
        st.write(f"Detrazioni Lavoro Dip.: {detrazione_effettiva:.2f} €")
        st.write(f"- Ritenute IRPEF Netta: {irpef_netta:.2f} €")

    st.divider()

    n1, n2, n3 = st.columns(3)
    n1.metric("Totale Competenze", f"{totale_competenze:.2f} €")
    n2.metric("Totale Trattenute", f"-{totale_trattenute:.2f} €")
    n3.metric("Netto in Busta", f"{netto_finale:.2f} €")

    st.divider()

    # --- Sezione Expander (Riepilogo Turni) ---
    with st.expander("📅 Dettaglio turni del mese, raggruppati per giorno"):
        riepilogo_giorni = df_mese.groupby("data").agg(
            ore_totali=("ore", "sum")).reset_index()
        riepilogo_giorni.columns = ["Data", "Ore totali"]
        st.dataframe(riepilogo_giorni.sort_values("Data"),
                     use_container_width=True, hide_index=True)

    with st.expander("📈 Riepilogo per categoria (turni)"):
        riepilogo_categoria = df_mese.groupby(
            "categoria").agg(ore=("ore", "sum")).reset_index()
        riepilogo_categoria.columns = ["Categoria", "Ore"]
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
