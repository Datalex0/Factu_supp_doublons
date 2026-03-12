import io
import os
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Suppression de doublons", layout="wide")
st.title("🧹 Suppression de doublons (XLSX / XLS / CSV)")

with st.expander("⚠️ Avertissement / Limitation de responsabilité 😜", expanded=False):
    st.markdown(
        """
        **Cette application est fournie “en l’état”.**  
        En utilisant cette application, vous reconnaissez que :
        - vous êtes responsable de vérifier les résultats avant toute utilisation,
        - vous conservez une copie de sauvegarde de vos fichiers d’origine,
        - l’éditeur décline toute responsabilité en cas de perte de données, d’erreur de traitement,
          ou de tout dommage direct ou indirect lié à l’utilisation de l’application.
        """
    )

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


def export_csv(df, sep=";"):
    # UTF-8 avec BOM pour ouverture clean dans Excel
    csv_bytes = df.to_csv(index=False, sep=sep).encode("utf-8-sig")
    return io.BytesIO(csv_bytes)

def normalize_for_dedup(s: pd.Series, trim: bool, ci: bool) -> pd.Series:
    # On ne touche pas aux données originales : on construit une clé de comparaison.
    x = s

    # On ne normalise que les colonnes "texte-like"
    if pd.api.types.is_string_dtype(x) or x.dtype == "object":
        x = x.astype(str)
        if trim:
            x = x.str.strip()
        if ci:
            # casefold() est plus robuste que lower() (accents, langues, etc.)
            x = x.str.casefold()
        return x

    # Pour les autres types (numériques, dates, etc.), on garde tel quel
    return x
 
 
def highlight_duplicates(df, col):
    """Retourne un DataFrame de styles : fond orange sur les lignes dupliquées."""
    normalized = normalize_for_dedup(df[col].copy(), trim=True, ci=True)
    is_dup = normalized.duplicated(keep=False)
 
    def style_row(row):
        if is_dup.iloc[row.name]:
            return ["background-color: #FFDAB9; color: #8B2500"] * len(row)
        return [""] * len(row)
 
    return df.style.apply(style_row, axis=1)


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


# ─────────────────────────────────────────────
# SECTION : MISE EN ÉVIDENCE DES DOUBLONS
# ─────────────────────────────────────────────
st.markdown("---")
st.subheader("🔍 Mise en évidence des doublons")
 
col_highlight, col_btn = st.columns([3, 1])
with col_highlight:
    highlight_col = st.selectbox(
        "Colonne à analyser",
        options=list(df.columns),
        key="highlight_col"
    )
with col_btn:
    st.write("")  # espace pour aligner le bouton
    st.write("")
    run_highlight = st.button("🎨 Mettre en évidence", type="secondary")
 
if run_highlight:
    normalized = normalize_for_dedup(df[highlight_col].copy(), trim=True, ci=True)
    is_dup = normalized.duplicated(keep=False)
    nb_dup_rows = is_dup.sum()
    nb_dup_vals = normalized[is_dup].nunique()
 
    if nb_dup_rows == 0:
        st.success(f"✅ Aucun doublon trouvé dans la colonne **{highlight_col}**.")
    else:
        st.warning(
            f"⚠️ **{nb_dup_rows} ligne(s)** concernées par des doublons "
            f"({nb_dup_vals} valeur(s) en double) dans la colonne **{highlight_col}**."
        )
        styled = highlight_duplicates(df, highlight_col)
        st.dataframe(styled, use_container_width=True)


# ─────────────────────────────────────────────
# SECTION : DÉDUPLICATION
# ─────────────────────────────────────────────
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
    case_insensitive = st.checkbox("Ignorer la casse (AZE = aze) pour la déduplication", value=True)





if st.button("Supprimer les doublons", type="primary"):
    before = len(df)

    # Colonnes utilisées pour la déduplication
    dedup_cols = list(df.columns) if subset is None else list(subset)

    df_key = df.copy()

    # Normalise uniquement les colonnes prises en compte
    for c in dedup_cols:
        df_key[c] = normalize_for_dedup(df_key[c], trim=trim_strings, ci=case_insensitive)

    # Déduplication faite sur df_key (normalisé) mais on récupère les lignes originales depuis df
    mask_keep = ~df_key.duplicated(subset=dedup_cols, keep=keep)
    df_clean = df.loc[mask_keep].reset_index(drop=True)
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
        out = export_csv(df_clean, sep=";")
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


