import io
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Suppression de doublons Excel", layout="centered")
st.title("🧹 Nettoyage Excel — suppression de doublons")

uploaded_file = st.file_uploader("Charge un fichier Excel (.xlsx)", type=["xlsx"])

if uploaded_file is not None:
    # Lecture de l'Excel (toutes les feuilles)
    try:
        xls = pd.ExcelFile(uploaded_file)
    except Exception as e:
        st.error(f"Impossible de lire le fichier Excel : {e}")
        st.stop()

    sheet_name = st.selectbox("Feuille à traiter", xls.sheet_names)

    try:
        df = pd.read_excel(xls, sheet_name=sheet_name)
    except Exception as e:
        st.error(f"Impossible de lire la feuille '{sheet_name}' : {e}")
        st.stop()

    st.subheader("Aperçu")
    st.dataframe(df, use_container_width=True)

    st.markdown("---")
    st.subheader("Paramètres de déduplication")

    col1, col2 = st.columns(2)

    with col1:
        dedup_scope = st.radio(
            "Dédupliquer sur :",
            ["Toutes les colonnes", "Colonnes sélectionnées"],
            horizontal=False,
        )

    with col2:
        keep_mode = st.selectbox("Conserver :", ["Première occurrence", "Dernière occurrence"])

    subset = None
    if dedup_scope == "Colonnes sélectionnées":
        subset = st.multiselect("Choisis les colonnes", options=list(df.columns))
        if not subset:
            st.warning("Sélectionne au moins une colonne pour dédupliquer.")
            st.stop()

    keep = "first" if keep_mode == "Première occurrence" else "last"

    if st.button("Supprimer les doublons", type="primary"):
        before = len(df)
        df_clean = df.drop_duplicates(subset=subset, keep=keep)
        after = len(df_clean)

        st.success(f"Doublons supprimés : {before - after} ligne(s) retirée(s).")
        st.subheader("Aperçu du résultat")
        st.dataframe(df_clean, use_container_width=True)

        # Export Excel en mémoire
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_clean.to_excel(writer, index=False, sheet_name=sheet_name)

        output.seek(0)

        # Nom de fichier de sortie
        original_name = uploaded_file.name.rsplit(".", 1)[0]
        out_name = f"{original_name}_sans_doublons.xlsx"

        st.download_button(
            label="⬇️ Télécharger le fichier nettoyé",
            data=output,
            file_name=out_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
else:
    st.info("Charge un fichier Excel pour commencer.")
