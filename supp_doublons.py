import io
import os
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Suppression de doublons", layout="centered")
st.title("🧹 Suppression de doublons (XLSX / XLS / CSV)")

uploaded_file = st.file_uploader("Charge un fichier (.xlsx, .xls, .csv)", type=["xlsx", "xls", "csv"])


def try_read_csv(uploaded, encoding=None, sep="AUTO"):
    uploaded.seek(0)

    # sep="AUTO" -> pandas essaie de deviner (avec engine="python")
    if sep == "AUTO" or sep is None:
        return pd.read_csv(uploaded, encoding=encoding, sep=None, engine="python")
    else:
        return pd.read_csv(uploaded, encoding=encoding, sep=sep)



def read_csv_robust(uploaded):
    # On essaye d'abord auto-sep avec encodages courants en France
    encodings_to_try = ["utf-8", "utf-8-sig", "cp1252", "latin1"]
    seps_to_try = ["AUTO", ";", ",", "\t", "|"]

    last_err = None
    for enc in encodings_to_try:
        for sep in seps_to_try:
            try:
                df = try_read_csv(uploaded, encoding=enc, sep=sep)
                return df, enc, sep
            except Exception as e:
                last_err = e
                continue

    raise last_err


def read_file(uploaded):
    name = uploaded.name.lower()
    ext = os.path.splitext(name)[1]

    if ext in [".xlsx", ".xls"]:
        xls = pd.ExcelFile(uploaded)
        return ext, xls, None

    if ext == ".csv":
        df, enc, sep = read_csv_robust(uploaded)
        return ext, df, {"encoding": enc, "sep": sep}

    raise ValueError("Format non supporté.")


def export_excel_single_sheet(df, sheet_name="Sheet1"):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name[:31])
    output.seek(0)
    return output


def export_csv(df):
    # UTF-8 avec BOM pour ouverture clean dans Excel
    csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
    return io.BytesIO(csv_bytes)


if uploaded_file is None:
    st.info("Charge un fichier pour commencer.")
    st.stop()

# --- Lecture principale
try:
    ext, obj, csv_meta = read_file(uploaded_file)
except Exception as e:
    st.error(f"Impossible de lire le fichier : {e}")
    st.stop()

sheet_name = None
if ext in [".xlsx", ".xls"]:
    xls = obj
    sheet_name = st.selectbox("Feuille à traiter", xls.sheet_names)
    df = pd.read_excel(xls, sheet_name=sheet_name)
else:
    df = obj

# Infos de lecture CSV
if ext == ".csv" and csv_meta:
    st.caption(f"CSV lu avec encoding **{csv_meta['encoding']}** et séparateur **{csv_meta['sep']}**")

    # Option de relecture manuelle si l’auto a “mal deviné”
    with st.expander("⚙️ Ajuster lecture CSV (si besoin)"):
        enc_choice = st.selectbox("Encodage", ["utf-8", "utf-8-sig", "cp1252", "latin1"], index=["utf-8","utf-8-sig","cp1252","latin1"].index(csv_meta["encoding"]))
        sep_choice = st.selectbox("Séparateur", ["AUTO", ";", ",", "\\t", "|"], index=["AUTO",";"," ,","\\t","|"].index(csv_meta["sep"]) if csv_meta["sep"] in ["AUTO",";","\\t","|"] else 0)

        if st.button("Relire le CSV avec ces paramètres"):
            sep_real = "\t" if sep_choice == "\\t" else sep_choice
            try:
                df = try_read_csv(uploaded_file, encoding=enc_choice, sep=sep_real)
                st.success("CSV relu ✅")
            except Exception as e:
                st.error(f"Échec relecture : {e}")
                st.stop()

st.subheader("Aperçu")
st.dataframe(df, use_container_width=True)

st.markdown("---")
st.subheader("Paramètres de déduplication")

col1, col2 = st.columns(2)
with col1:
    dedup_scope = st.radio("Dédupliquer sur :", ["Toutes les colonnes", "Colonnes sélectionnées"])
with col2:
    keep_mode = st.selectbox("Conserver :", ["Première occurrence", "Dernière occurrence"])

subset = None
if dedup_scope == "Colonnes sélectionnées":
    subset = st.multiselect("Colonnes", options=list(df.columns))
    if not subset:
        st.warning("Sélectionne au moins une colonne.")
        st.stop()

keep = "first" if keep_mode == "Première occurrence" else "last"

with st.expander("Options avancées"):
    trim_strings = st.checkbox("Nettoyer les espaces (strip) sur les colonnes texte", value=False)

df_work = df.copy()
if trim_strings:
    for c in df_work.columns:
        if pd.api.types.is_string_dtype(df_work[c]):
            df_work[c] = df_work[c].astype(str).str.strip()

if st.button("Supprimer les doublons", type="primary"):
    before = len(df_work)
    df_clean = df_work.drop_duplicates(subset=subset, keep=keep)
    after = len(df_clean)

    st.success(f"✅ {before - after} doublon(s) supprimé(s).")

    colA, colB, colC = st.columns(3)
    colA.metric("Lignes avant", before)
    colB.metric("Lignes après", after)
    colC.metric("Différence", before - after)

    st.caption(f"Aperçu : {after} lignes dans le fichier nettoyé.")
    st.dataframe(df_clean, use_container_width=True)

    base = os.path.splitext(uploaded_file.name)[0]

    if ext == ".csv":
        out = export_csv(df_clean)
        out_name = f"{base}_sans_doublons.csv"
        mime = "text/csv"
    else:
        out = export_excel_single_sheet(df_clean, sheet_name=sheet_name or "Sheet1")
        out_name = f"{base}_sans_doublons.xlsx"
        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    st.download_button(
        "⬇️ Télécharger le fichier nettoyé",
        data=out,
        file_name=out_name,
        mime=mime,
    )
