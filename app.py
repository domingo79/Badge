"""
Conteggio Ore & Stima Stipendio - App Streamlit (v3)

Novità rispetto alla v2:
- Le "voci stipendio" sono ora separate come in busta paga: una riga per le
  ore lavorate a tariffa base, e righe distinte per ogni maggiorazione
  (domenicale, notturno, festivo) e ogni rateo (13ª, 14ª, ferie, ROL, formazione),
  invece di un unico importo per turno con moltiplicatore incorporato.
- Detrazione lavoro dipendente calcolata sui giorni retribuiti (non sulle ore),
  formula calibrata sul cedolino di giugno 2026: 1.380 €/anno * giorni/365.
"""

import streamlit as st
import pandas as pd
from datetime import date
import os

CSV_PATH = "turni.csv"
# Soglia CCNL, confermata dalla busta paga (1491.57 / 172 = 8.67192 €/h)
SOGLIA_MENSILE_ORE = 172

# 6° livello CCNL Turismo/Pubblici Esercizi, minimo tabellare mensile / 172h.
RETRIBUZIONE_MENSILE_DEFAULT = 1491.57
PAGA_ORARIA_DEFAULT = RETRIBUZIONE_MENSILE_DEFAULT / SOGLIA_MENSILE_ORE

# Percentuali maggiorazione realmente legate a turni EFFETTIVAMENTE lavorati.
PERC_DOMENICALE_DEFAULT = 0.10   # confermato: 0.86719 * 19h = 16.48 € in busta paga
PERC_NOTTURNO_DEFAULT = 0.60     # non ancora verificato su busta paga reale

# Ratei 13ª/14ª/ferie: (ore_lavorate_non_formazione / divisore) * paga_oraria
DIVISORE_RATEI_DEFAULT = 12.0

# Contributi INPS/enti bilaterali, calibrati sulla busta paga di giugno 2026:
# IVS 9.19% + FIS 0.26667% + CIGS 0.30% + E.B.T. 0.20%
PERC_INPS_DEFAULT = 0.0995667

# Scaglioni IRPEF annui (irpef progressiva). Verifica sempre coi valori aggiornati.
IRPEF_SCAGLIONI = [(28000, 0.23), (50000, 0.35), (float("inf"), 0.43)]

# Detrazione lavoro dipendente: per contratto a tempo determinato con reddito
# annuo basso, minimo garantito 1.380 €/anno, rapportato ai giorni retribuiti.
# Verificato: 1380 * 19gg / 365 = 71,84 € (torna esatto sul cedolino di giugno).
DETRAZIONE_ANNUA_DEFAULT = 1380.0

COLONNE = ["data", "etichetta", "ore", "domenicale",
           "notturno", "festivo", "formazione"]


def calcola_irpef_lorda_annua(reddito_annuo: float) -> float:
    imposta = 0.0
    soglia_prec = 0.0
    for soglia, aliquota in IRPEF_SCAGLIONI:
        if reddito_annuo > soglia_prec:
            base = min(reddito_annuo, soglia) - soglia_prec
            imposta += base * aliquota
            soglia_prec = soglia
        else:
            break
    return imposta


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


def calcola_voci_stipendio(df_mese: pd.DataFrame, paga_oraria: float,
                           perc_domenicale: float, perc_notturno: float,
                           divisore_ratei: float, ore_rol_manuale: float,
                           ore_festivita_manuale: float) -> pd.DataFrame:
    """Ricostruisce le voci di stipendio come righe separate, sullo stile
    della busta paga: ore base, maggiorazioni su turni effettivi, ratei —
    ognuna con la propria base oraria e il proprio importo.

    NB: 'Festività infrasettimanali non godute' NON dipende dai turni marcati
    come festivi: nei contratti a chiamata è un rateo maturato a prescindere,
    come ferie/13ª/14ª/ROL, per compensare le festività che non puoi goderti
    non avendo giorni di riposo fissi. Va quindi inserito manualmente finché
    non si individua la formula esatta su più cedolini."""
    non_formazione = df_mese.loc[~df_mese["formazione"]]
    formazione = df_mese.loc[df_mese["formazione"]]

    ore_base = non_formazione["ore"].sum()
    ore_domenicale = non_formazione.loc[non_formazione["domenicale"], "ore"].sum(
    )
    ore_notturno = non_formazione.loc[non_formazione["notturno"], "ore"].sum()
    ore_formazione = formazione["ore"].sum()

    ore_rateo = ore_base / divisore_ratei if divisore_ratei else 0.0

    voci = [
        {"voce": "Ore lavorate", "base": ore_base, "unita": "h",
         "tariffa": paga_oraria, "importo": ore_base * paga_oraria},
        {"voce": "Maggiorazione domenicale", "base": ore_domenicale, "unita": "h",
         "tariffa": paga_oraria * perc_domenicale,
         "importo": ore_domenicale * paga_oraria * perc_domenicale},
        {"voce": "Maggiorazione notturno", "base": ore_notturno, "unita": "h",
         "tariffa": paga_oraria * perc_notturno,
         "importo": ore_notturno * paga_oraria * perc_notturno},
        {"voce": "Formazione", "base": ore_formazione, "unita": "h",
         "tariffa": paga_oraria, "importo": ore_formazione * paga_oraria},
        {"voce": "Rateo 13ª", "base": ore_rateo, "unita": "h",
         "tariffa": paga_oraria, "importo": ore_rateo * paga_oraria},
        {"voce": "Rateo 14ª", "base": ore_rateo, "unita": "h",
         "tariffa": paga_oraria, "importo": ore_rateo * paga_oraria},
        {"voce": "Ferie non godute", "base": ore_rateo, "unita": "h",
         "tariffa": paga_oraria, "importo": ore_rateo * paga_oraria},
        {"voce": "Festività infrasettimanali non godute", "base": ore_festivita_manuale, "unita": "h",
         "tariffa": paga_oraria, "importo": ore_festivita_manuale * paga_oraria},
        {"voce": "Permessi ROL non goduti", "base": ore_rol_manuale, "unita": "h",
         "tariffa": paga_oraria, "importo": ore_rol_manuale * paga_oraria},
    ]
    voci_df = pd.DataFrame(voci)
    return voci_df[voci_df["base"] > 0].reset_index(drop=True)


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
        "Paga oraria base (€) — dalla busta paga",
        min_value=0.0, value=PAGA_ORARIA_DEFAULT, step=0.01, format="%.2f"
    )
    retribuzione_mensile = st.number_input(
        "Retribuzione mensile teorica (€)",
        min_value=0.0, value=RETRIBUZIONE_MENSILE_DEFAULT, step=0.01, format="%.2f"
    )

    st.caption(
        "Maggiorazioni su turni effettivi — riga separata sulle proprie ore")
    perc_domenicale = st.number_input(
        "Domenicale %", min_value=0.0, value=PERC_DOMENICALE_DEFAULT * 100, step=1.0) / 100
    perc_notturno = st.number_input(
        "Notturno %", min_value=0.0, value=PERC_NOTTURNO_DEFAULT * 100, step=1.0) / 100

    st.caption("Divisore ratei (13ª/14ª/ferie) — ore lavorate / divisore")
    divisore_ratei = st.number_input(
        "Divisore", min_value=1.0, value=DIVISORE_RATEI_DEFAULT, step=1.0)

    st.caption(
        "Festività infrasettimanali non godute e Permessi ROL non goduti sono "
        "ratei maturati indipendentemente dai turni (tipico dei contratti a "
        "chiamata) — inseriscili manualmente guardando il cedolino, finché "
        "non individuiamo la formula esatta su più mensilità."
    )
    ore_festivita_manuale = st.number_input(
        "Ore festività infrasettimanali non godute nel mese", min_value=0.0, value=0.0, step=0.1)
    ore_rol_manuale = st.number_input(
        "Ore ROL accantonate nel mese", min_value=0.0, value=0.0, step=0.1)

    st.header("💸 Stima netto")
    perc_inps = st.number_input(
        "Contributi INPS/enti bilaterali %", min_value=0.0,
        value=PERC_INPS_DEFAULT * 100, step=0.01, format="%.5f") / 100
    detrazione_annua = st.number_input(
        "Detrazione lavoro dipendente annua (€) — dipende da reddito/contratto",
        min_value=0.0, value=DETRAZIONE_ANNUA_DEFAULT, step=10.0)

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

    delta = ore_totali_mese - SOGLIA_MENSILE_ORE
    if delta >= 0:
        st.success(
            f"Hai superato la soglia di {SOGLIA_MENSILE_ORE}h di {delta:.2f} ore")
    else:
        st.warning(
            f"Mancano {abs(delta):.2f} ore per raggiungere la soglia di {SOGLIA_MENSILE_ORE}h")

    # --- Voci stipendio: una riga per ogni componente, come in busta paga ---
    st.subheader("🧾 Voci stipendio")
    voci_df = calcola_voci_stipendio(
        df_mese, paga_oraria, perc_domenicale, perc_notturno,
        divisore_ratei, ore_rol_manuale, ore_festivita_manuale
    )
    voci_display = voci_df.drop(columns=["unita"]).copy()
    voci_display["base"] = voci_display["base"].map(lambda x: f"{x:.2f} h")
    voci_display["tariffa"] = voci_display["tariffa"].map(
        lambda x: f"{x:.4f} €/h")
    voci_display["importo"] = voci_display["importo"].map(
        lambda x: f"{x:.2f} €")
    voci_display.columns = ["Voce", "Ore/base", "Tariffa", "Importo"]
    st.dataframe(voci_display, use_container_width=True, hide_index=True)

    totale_complessivo = voci_df["importo"].sum()
    st.metric("💰 Totale lordo (somma voci)", f"{totale_complessivo:.2f} €")

    st.caption(
        "Ogni riga è calcolata separatamente sulle proprie ore, come in busta paga: "
        "'Ore lavorate' è la tariffa base su tutte le ore non di formazione; le "
        "maggiorazioni sono importi aggiuntivi solo sulle ore marcate con quel flag; "
        "i ratei (13ª/14ª/ferie) sono ore_lavorate/divisore × paga oraria."
    )

    # --- Stima netto ---
    st.subheader("💸 Stima netto")
    contributi_inps = totale_complessivo * perc_inps
    imponibile_irpef = totale_complessivo - contributi_inps
    irpef_lorda_mese = calcola_irpef_lorda_annua(imponibile_irpef * 12) / 12

    detrazione_effettiva = detrazione_annua * giorni_retribuiti / 365
    irpef_netta_mese = max(0.0, irpef_lorda_mese - detrazione_effettiva)

    stima_netto = totale_complessivo - contributi_inps - irpef_netta_mese

    n1, n2, n3 = st.columns(3)
    n1.metric("Contributi INPS", f"-{contributi_inps:.2f} €")
    n2.metric("IRPEF netta", f"-{irpef_netta_mese:.2f} €")
    n3.metric("Stima netto in busta", f"{stima_netto:.2f} €")

    st.caption(
        f"Imponibile IRPEF = {totale_complessivo:.2f} − {contributi_inps:.2f} = {imponibile_irpef:.2f} €. "
        f"IRPEF lorda (primo scaglione 23%, annualizzata) = {irpef_lorda_mese:.2f} €. "
        f"Detrazione = {detrazione_annua:.0f} €/anno × {giorni_retribuiti} giorni / 365 "
        f"= {detrazione_effettiva:.2f} €. "
        "⚠️ Formula calibrata sul primo cedolino (tempo determinato, reddito annuo sotto 15.000 €): "
        "se cambia lo scaglione di reddito la detrazione ufficiale (art. 13 TUIR) cambia formula. "
        "Non è consulenza fiscale, verifica sempre sui cedolini reali."
    )

    st.caption(
        "⚠️ Stima indicativa: non considera scatti di anzianità, TFR o altre voci minori "
        "in busta paga. Verifica sempre con la busta paga reale o con il consulente del lavoro."
    )

    with st.expander("Dettaglio turni del mese, raggruppati per giorno"):
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
