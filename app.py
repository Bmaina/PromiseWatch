"""
PromiseWatch — Streamlit frontend
==================================
Reads promisewatch_cases_v4.csv (sourced claims) and
resolved_results.json (real Earth Engine pipeline output, captured
ahead of time so this app works over low-bandwidth connections and
doesn't require every visitor to have Earth Engine credentials).

Run locally:   pip install streamlit pandas
               streamlit run app.py

Deploy free:   push to GitHub, connect the repo at
               share.streamlit.io — this gives judges a live link
               instead of a Colab notebook.
"""

import json
import os
import pandas as pd
import streamlit as st

HERE = os.path.dirname(os.path.abspath(__file__))

STRINGS = {
    "en": {
        "title": "PROMISEWATCH",
        "subtitle": "Search public infrastructure commitments — independent evidence from satellite imagery",
        "search_placeholder": "Search projects...",
        "county_all": "All counties",
        "status_all": "All statuses",
        "view_case": "VIEW CASE →",
        "back": "← ALL COMMITMENTS",
        "what_promised": "WHAT WAS PROMISED",
        "contracted": "Contracted",
        "design_reservoir": "Design reservoir",
        "source_info": "Source information",
        "what_evidence": "WHAT SATELLITE EVIDENCE SHOWS",
        "baseline": "BASELINE",
        "current": "CURRENT",
        "baseline_unavailable": "Baseline-period image not included in this demo build — only the current-period composite is shown. The pipeline computes a real baseline value (below); the image itself wasn't exported for this app.",
        "water_added": "Water added since baseline",
        "why_conclusion": "WHY THIS CONCLUSION",
        "guardrail_label": "Guardrail",
        "guardrail_explain": "The system compares water added since the baseline rather than simply asking whether water exists — a claim isn't supported just because some water is visible nearby.",
        "human_verification": "HUMAN VERIFICATION",
        "visually_checked": "Satellite result visually checked against the raw imagery by a person before being reported",
        "checked_label": "Checked",
        "next_steps": "WHAT YOU CAN DO NEXT",
        "review_sources": "Review the underlying sources",
        "view_evidence": "View satellite evidence image",
        "report_eacc": "Report suspected irregularity to EACC",
        "not_evaluated": "NOT YET EVALUATED",
        "not_evaluated_text": "Road and stadium detection are not yet implemented in this build — this case is documented with a sourced claim but has no satellite verdict yet.",
        "no_results": "No projects match your search.",
        "lang_toggle": "Language / Lugha",
    },
    "sw": {
        "title": "PROMISEWATCH",
        "subtitle": "Tafuta ahadi za miundombinu ya umma — ushahidi huru kutoka picha za setilaiti",
        "search_placeholder": "Tafuta miradi...",
        "county_all": "Kaunti zote",
        "status_all": "Hali zote",
        "view_case": "ANGALIA KESI →",
        "back": "← AHADI ZOTE",
        "what_promised": "KILICHOAHIDIWA",
        "contracted": "Ilikabidhiwa",
        "design_reservoir": "Bwawa lililopangwa",
        "source_info": "Taarifa za chanzo",
        "what_evidence": "USHAHIDI WA SETILAITI UNAONYESHA NINI",
        "baseline": "AWALI",
        "current": "SASA",
        "baseline_unavailable": "Picha ya kipindi cha awali haijajumuishwa katika jaribio hili — ni picha ya sasa pekee inayoonyeshwa. Mfumo huhesabu thamani halisi ya awali (chini); picha yenyewe haikutolewa kwa programu hii.",
        "water_added": "Maji yaliyoongezeka tangu awali",
        "why_conclusion": "KWA NINI HITIMISHO HILI",
        "guardrail_label": "Kiwango cha chini",
        "guardrail_explain": "Mfumo hulinganisha maji yaliyoongezeka tangu awali badala ya kuuliza tu kama maji yapo — dai halithibitishwi kwa sababu tu kuna maji karibu.",
        "human_verification": "UTHIBITISHO WA BINADAMU",
        "visually_checked": "Matokeo ya setilaiti yalikaguliwa kwa macho dhidi ya picha halisi na mtu kabla ya kuripotiwa",
        "checked_label": "Ilikaguliwa",
        "next_steps": "UNACHOWEZA KUFANYA SASA",
        "review_sources": "Kagua vyanzo vya msingi",
        "view_evidence": "Angalia picha ya ushahidi wa setilaiti",
        "report_eacc": "Ripoti ukiukwaji unaoshukiwa kwa EACC",
        "not_evaluated": "BADO HAIJATATHMINIWA",
        "not_evaluated_text": "Utambuzi wa barabara na uwanja bado haujatekelezwa katika toleo hili — kesi hii ina dai lenye chanzo lakini haina hitimisho la setilaiti bado.",
        "no_results": "Hakuna miradi inayolingana na utafutaji wako.",
        "lang_toggle": "Language / Lugha",
    },
}

st.set_page_config(page_title="PromiseWatch", layout="wide")


@st.cache_data
def load_data():
    cases = pd.read_csv(os.path.join(HERE, "promisewatch_cases_v4.csv"))
    with open(os.path.join(HERE, "resolved_results.json")) as f:
        resolved = json.load(f)["results"]
    return cases, resolved


cases_df, resolved = load_data()

if "lang" not in st.session_state:
    st.session_state.lang = "en"
if "selected_case" not in st.session_state:
    st.session_state.selected_case = None

lang_choice = st.sidebar.radio(
    STRINGS["en"]["lang_toggle"], ["English", "Kiswahili"],
    index=0 if st.session_state.lang == "en" else 1,
)
st.session_state.lang = "en" if lang_choice == "English" else "sw"
T = STRINGS[st.session_state.lang]

st.sidebar.caption(
    "Note: this toggle translates the interface — case claims, sources, and "
    "evidence descriptions remain in their original sourced language (English)."
    if st.session_state.lang == "en" else
    "Kumbuka: kitufe hiki kinatafsiri kiolesura — madai ya kesi, vyanzo, na "
    "maelezo ya ushahidi yanabaki katika lugha ya awali ya chanzo (Kiingereza)."
)


def evidence_image_path(project_name):
    filename = project_name.replace(" ", "_") + ".png"
    p = os.path.join(HERE, "evidence", filename)
    return p if os.path.exists(p) else None


def status_badge(status):
    if status == "SUPPORTED":
        return "🟢 SUPPORTED"
    elif status and "NOT DELIVERED" in status:
        return "🔴 NOT DELIVERED / CONFLICTED"
    else:
        return "⚪ " + T["not_evaluated"]


def render_browser():
    st.title(T["title"])
    st.caption(T["subtitle"])

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        search = st.text_input(T["search_placeholder"], label_visibility="collapsed",
                                placeholder=T["search_placeholder"])
    with col2:
        counties = [T["county_all"]] + sorted(cases_df["county"].unique().tolist())
        county = st.selectbox(T["county_all"], counties, label_visibility="collapsed")
    with col3:
        statuses = [T["status_all"], "SUPPORTED", "NOT DELIVERED / CONFLICTED", T["not_evaluated"]]
        status_filter = st.selectbox(T["status_all"], statuses, label_visibility="collapsed")

    filtered = cases_df.copy()
    if search:
        filtered = filtered[filtered["project_name"].str.contains(search, case=False, na=False)]
    if county != T["county_all"]:
        filtered = filtered[filtered["county"] == county]

    st.divider()

    if len(filtered) == 0:
        st.info(T["no_results"])
        return

    for _, row in filtered.iterrows():
        name = row["project_name"]
        result = resolved.get(name)
        status = result["verdict_status"] if result else None

        if status_filter != T["status_all"]:
            display_status = status if status else T["not_evaluated"]
            if status_filter != display_status:
                continue

        with st.container(border=True):
            c1, c2 = st.columns([4, 1])
            with c1:
                st.markdown(f"### {name}")
                st.caption(row["county"])
                st.markdown(f"**{status_badge(status)}**")
                if result:
                    if status == "SUPPORTED":
                        st.write(f"{result['delta_ha']} ha new water detected")
                    else:
                        st.write(result["verdict_text"][:80] + "...")
                else:
                    st.write(T["not_evaluated_text"][:80] + "...")
            with c2:
                if st.button(T["view_case"], key=f"view_{name}"):
                    st.session_state.selected_case = name
                    st.rerun()


def render_case(name):
    row = cases_df[cases_df["project_name"] == name].iloc[0]
    result = resolved.get(name)

    if st.button(T["back"]):
        st.session_state.selected_case = None
        st.rerun()

    st.title(name)
    st.subheader(status_badge(result["verdict_status"] if result else None))
    st.caption(f"{row['county']}, Kenya")

    st.divider()
    st.markdown(f"#### {T['what_promised']}")
    c1, c2 = st.columns(2)
    with c1:
        st.write(f"**{T['contracted']}:** {row['promise_or_start_date']}")
    with c2:
        if pd.notna(row.get("design_reservoir_note", None)):
            pass
    st.write(row["reported_status_as_of_2026"])
    st.markdown(f"[{T['source_info']}]({row['source_url']})")

    st.divider()
    st.markdown(f"#### {T['what_evidence']}")

    if result:
        img_path = evidence_image_path(name)
        ic1, ic2 = st.columns(2)
        with ic1:
            st.markdown(f"**{T['baseline']}**")
            st.info(T["baseline_unavailable"])
            st.metric(T["baseline"], f"{result['pre_extent_ha']} ha", label_visibility="collapsed")
        with ic2:
            st.markdown(f"**{T['current']}**")
            if img_path:
                st.image(img_path, width="stretch")
            st.metric(T["current"], f"{result['current_extent_ha']} ha", label_visibility="collapsed")

        st.metric(T["water_added"], f"{result['delta_ha']} ha")

        st.divider()
        st.markdown(f"#### {T['why_conclusion']}")
        st.write(f"**{T['guardrail_label']}:** {result['guardrail_min_ha']} ha")
        st.write(T["guardrail_explain"])
        st.write(result["verdict_text"])

        st.divider()
        st.markdown(f"#### {T['human_verification']}")
        check_mark = "✓" if result.get("visually_confirmed") else "⚠"
        st.write(f"{check_mark} {T['visually_checked']}")
        st.caption(f"{T['checked_label']}: {result['checked_on']}")

        st.divider()
        st.markdown(f"#### {T['next_steps']}")
        st.markdown(f"- [{T['review_sources']}]({row['source_url']})")
        if img_path:
            st.markdown(f"- {T['view_evidence']} (above)")
        if result["verdict_status"] != "SUPPORTED":
            action = row.get("suggested_action_if_not_delivered", "")
            st.markdown(f"- **{T['report_eacc']}**: {action}")
    else:
        st.warning(T["not_evaluated_text"])
        action = row.get("suggested_action_if_not_delivered", "")
        if isinstance(action, str) and action:
            st.markdown(f"**{T['next_steps']}**")
            st.write(action)


if st.session_state.selected_case:
    render_case(st.session_state.selected_case)
else:
    render_browser()
