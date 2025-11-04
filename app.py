# app.py
import streamlit as st
import json
import pandas as pd
from io import StringIO
from typing import Dict, List, Tuple
from functools import lru_cache

st.set_page_config(page_title="NBA Pronostics - Comparateur", layout="wide")

# -------------------------
# Configuration / Defaults
# -------------------------
DEFAULT_SCORING = {
    "exact": 3,   # même position
    "near1": 0,   # +/-1
    "near2": 0    # +/-2
}

# -------------------------
# Utility: Load pronostics
# -------------------------
def load_pronostics_from_file(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_pronostics_from_uploaded(uploaded_file) -> Dict:
    if uploaded_file is None:
        return {}
    s = StringIO(uploaded_file.getvalue().decode("utf-8"))
    return json.load(s)

# -------------------------
# Scoring logic
# -------------------------
def calcul_score(pronostic: List[str], classement_reel: List[str], scoring: Dict = DEFAULT_SCORING) -> Tuple[int, Dict[str,int]]:
    """
    Retourne (score_total, detail_par_equipe)
    Rules:
      - exact: même index -> scoring['exact']
      - distance 1 -> scoring['near1']
      - distance 2 -> scoring['near2']
    """
    score = 0
    details = {}
    for i, team in enumerate(pronostic):
        points = 0
        if team in classement_reel:
            idx = classement_reel.index(team)
            diff = abs(i - idx)
            if diff == 0:
                points = scoring.get("exact", 3)
            elif diff == 1:
                points = scoring.get("near1", 2)
            elif diff == 2:
                points = scoring.get("near2", 1)
        details[team] = points
        score += points
    return score, details

# -------------------------
# Standings (mock + API placeholder)
# -------------------------
@lru_cache(maxsize=1)
def get_live_standings_mock() -> Dict[str, List[str]]:
    """
    Donne un classement factice (mock). Remplace par une fonction qui appelle une API réelle.
    Exemple : renvoyer les 15 premières équipes pour chaque conférence.
    """
    return {
        "Est": ["Celtics", "Bucks", "Knicks", "76ers", "Heat", "Pacers", "Bulls", "Hawks", "Cavaliers", "Hornets", "Pistons", "Wizards", "Raptors", "Magic", "Nets"],
        "Ouest": ["Nuggets", "Thunder", "Mavericks", "Timberwolves", "Clippers", "Suns", "Warriors", "Pelicans", "Grizzlies", "Trail Blazers", "Kings", "Spurs", "Lakers", "Jazz", "Rockets"]
    }

# -------------------------
# Standings via nba_api
# -------------------------
from nba_api.stats.endpoints import leaguestandings

@lru_cache(maxsize=1)
def get_live_standings_nba_api() -> Dict[str, List[str]]:
    """
    Récupère le classement NBA actuel en utilisant nba_api.
    Retourne un dict : {"Est": [...], "Ouest": [...]}
    """
    try:
        data = leaguestandings.LeagueStandings().get_data_frames()[0]

        east = (
            data[data["Conference"] == "East"]
            .sort_values("PlayoffRank")[["TeamCity", "TeamName"]]
        )
        west = (
            data[data["Conference"] == "West"]
            .sort_values("PlayoffRank")[["TeamCity", "TeamName"]]
        )

        est_list = [f"{city} {name}" for city, name in zip(east["TeamCity"], east["TeamName"])]
        ouest_list = [f"{city} {name}" for city, name in zip(west["TeamCity"], west["TeamName"])]

        return {"Est": est_list, "Ouest": ouest_list}
    except Exception as e:
        st.error(f"Erreur lors de la récupération du classement NBA : {e}")
        return get_live_standings_mock()  # fallback


# -------------------------
# UI : Sidebar
# -------------------------
st.sidebar.title("Configuration")
st.sidebar.markdown("**Charge les pronostics** (fichier JSON) ou utilise l'exemple intégré.")
uploaded = st.sidebar.file_uploader("Uploader pronostics.json", type=["json"])

use_example = st.sidebar.checkbox("Utiliser l'exemple intégré (pronostics.json)", value=True)
scoring_exact = st.sidebar.number_input("Points (exact)", value=DEFAULT_SCORING["exact"], min_value=0, max_value=10)
scoring_near1 = st.sidebar.number_input("Points (±1)", value=DEFAULT_SCORING["near1"], min_value=0, max_value=10)
scoring_near2 = st.sidebar.number_input("Points (±2)", value=DEFAULT_SCORING["near2"], min_value=0, max_value=10)

scoring_config = {"exact": scoring_exact, "near1": scoring_near1, "near2": scoring_near2}

# Load pronostics
pronostics = {}
if uploaded:
    try:
        pronostics = load_pronostics_from_uploaded(uploaded)
        st.sidebar.success("Pronostics chargés depuis le fichier uploadé.")
    except Exception as e:
        st.sidebar.error(f"Erreur lecture fichier: {e}")
        pronostics = {}
elif use_example:
    try:
        pronostics = load_pronostics_from_file("pronostics.json")
        st.sidebar.success("Pronostics chargés depuis pronostics.json local.")
    except FileNotFoundError:
        st.sidebar.warning("pronostics.json local introuvable — utilise l'upload ou crée le fichier.")
        pronostics = {}

# Choose standings source (for now mock)
standings_source = st.sidebar.selectbox("Source des standings", ["NBA API (live)", "Mock (local)"])

if standings_source == "Mock (local)":
    standings = get_live_standings_mock()
else:
    st.sidebar.success("Classement récupéré via nba_api 📡")
    standings = get_live_standings_nba_api()

# -------------------------
# Main UI
# -------------------------
st.title("🏀 Comparateur de pronostics NBA")
st.markdown("Compare plusieurs pronostics au classement réel et calcule des points.")

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("Classement réel (utilisé pour le scoring)")
    st.markdown("**Conférence Est**")
    st.write(standings["Est"])
    st.markdown("**Conférence Ouest**")
    st.write(standings["Ouest"])

with col2:
    st.subheader("Règles de scoring")
    st.write(f"Exact = {scoring_config['exact']} pts")
    st.write(f"±1 = {scoring_config['near1']} pts")
    st.write(f"±2 = {scoring_config['near2']} pts")
    st.markdown("---")
    st.write(f"Nombre de pronostics chargés: **{len(pronostics)}**")

# -------------------------
# Compute scores for each player
# -------------------------
if not pronostics:
    st.warning("Aucun pronostic chargé — upload un fichier JSON ou crée 'pronostics.json' local.")
    st.stop()

results = []
details_all = {}

for joueur, prono in pronostics.items():
    est_prono = prono.get("Est", [])
    ouest_prono = prono.get("Ouest", [])
    score_est, details_est = calcul_score(est_prono, standings["Est"], scoring=scoring_config)
    score_ouest, details_ouest = calcul_score(ouest_prono, standings["Ouest"], scoring=scoring_config)
    total = score_est + score_ouest
    results.append({
        "Joueur": joueur,
        "Score Est": score_est,
        "Score Ouest": score_ouest,
        "Total": total
    })
    details_all[joueur] = {"Est": details_est, "Ouest": details_ouest}

df_results = pd.DataFrame(results)
df_results = df_results.sort_values(by="Total", ascending=False).reset_index(drop=True)

# -------------------------
# Display leaderboard and details
# -------------------------
st.subheader("Classement des pronostics")
st.dataframe(df_results.style.format({"Total": "{:.0f}"}), use_container_width=True)

# Per-player detail expanders
st.subheader("Détails par joueur")
for joueur in df_results["Joueur"].tolist():
    with st.expander(f"{joueur} — Total = {df_results[df_results['Joueur']==joueur]['Total'].values[0]} pts"):
        st.write("Score Est:", df_results[df_results['Joueur']==joueur]["Score Est"].values[0])
        st.write("Score Ouest:", df_results[df_results['Joueur']==joueur]["Score Ouest"].values[0])
        st.markdown("**Détail des points par équipe (Est)**")
        st.table(pd.DataFrame.from_dict(details_all[joueur]["Est"], orient="index", columns=["Points"]).reset_index().rename(columns={"index":"Equipe"}))
        st.markdown("**Détail des points par équipe (Ouest)**")
        st.table(pd.DataFrame.from_dict(details_all[joueur]["Ouest"], orient="index", columns=["Points"]).reset_index().rename(columns={"index":"Equipe"}))

# -------------------------
# Side-by-side comparison: classement réel vs pronostic d'un joueur sélectionné
# -------------------------
st.subheader("Comparer un pronostic avec le classement réel")
player_select = st.selectbox("Choisir un joueur", df_results["Joueur"].tolist())

prono_sel = pronostics[player_select]
left, right = st.columns(2)
with left:
    st.markdown("**Classement réel - Est**")
    st.write(pd.DataFrame({"Position": list(range(1, len(standings["Est"])+1)), "Equipe": standings["Est"]}))
with right:
    st.markdown(f"**Pronostic {player_select} - Est**")
    st.write(pd.DataFrame({"Position": list(range(1, len(prono_sel.get('Est', []))+1)), "Equipe": prono_sel.get("Est", [])}))

left2, right2 = st.columns(2)
with left2:
    st.markdown("**Classement réel - Ouest**")
    st.write(pd.DataFrame({"Position": list(range(1, len(standings["Ouest"])+1)), "Equipe": standings["Ouest"]}))
with right2:
    st.markdown(f"**Pronostic {player_select} - Ouest**")
    st.write(pd.DataFrame({"Position": list(range(1, len(prono_sel.get('Ouest', []))+1)), "Equipe": prono_sel.get("Ouest", [])}))

# -------------------------
# Export CSV
# -------------------------
st.subheader("Export / Téléchargement")
csv = df_results.to_csv(index=False).encode("utf-8")
st.download_button("Télécharger le classement des pronostics (CSV)", data=csv, file_name="classement_pronostics.csv", mime="text/csv")

st.info("Astuce : tu peux modifier les règles de scoring dans la barre latérale et recharger pour voir les effets.")
