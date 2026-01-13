import io
import os
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Suppression de doublons", layout="centered")
st.title("🧹 Suppression de doublons (XLSX / XLS / CSV)")

uploaded_file = st.file_uploader("Charge un fichier (.xlsx, .xls, .csv)", type=["xlsx", "xls", "csv"])

def read_file(uploaded):
    name = uploaded.name.lower()
    ext = os.path.splitext(name)[1]

    if ext in [".xlsx", ".xls"]:
        # Excel : on lit les feuilles pour proposer un choix
        xls = pd.ExcelFile(uploaded)
        return ext, xls
    elif ext == ".csv":
        # CSV : on essaye quelques séparateurs courants
        uploaded.seek(0)
        try:
            df = pd.read_csv(uploaded, sep=None, engine="python")  # auto-détection
        except Exception:
            uploaded.seek(0)
            df = pd.read_csv(uploaded, sep=";")
        return ext, df
    else:
        raise ValueError("Format non supporté.")

def export_excel_single_sheet(df, sheet_name="Sheet1"):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name[:31])  # limite Excel 31 chars
    output.seek(0)
    return output

def export_csv(df):
    # UTF-8 avec BOM pour éviter les soucis d’accents dans Excel
    csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
    return io.BytesIO(csv_bytes)

if uploaded_file is None:
    st.info("Charge un fichier pour commencer.")
    st.stop()

# --- Lecture
try:
    ext, obj = read_file(uploaded_file)
except Exception as e:
    st.error(f"Impossible de lire le fichier : {e}")
    st.stop()

sheet_name = None
if ext in [".xlsx", ".xls"]:
    xls = obj
    sheet_name = st.selectbox("Feuille à traiter", xls.sheet_names)
    try:
        df = pd.read_excel(xls, sheet_name=sheet_name)
    except Exception as e:
        st.error(f"Impossible de lire la feuille '{sheet_name}' : {e}")
        st.stop()
else:
    df = obj

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

# Option utile quand on a des “faux doublons” (espaces, casse)
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
    st.subheader("Aperçu du résultat")
    st.dataframe(df_clean, use_container_width=True)

    base = os.path.splitext(uploaded_file.name)[0]

    # --- Export dans le même "esprit" :
    # CSV -> CSV
    # XLS/XLSX -> XLSX (pandas exporte en xlsx via openpyxl)
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
