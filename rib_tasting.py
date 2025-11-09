import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import json

# Page config
st.set_page_config(page_title="Blind Rib Tasting", page_icon="🍖", layout="wide")

# Categories and rib sets
CATEGORIES = {
    'tenderness': {'name': 'Tenderness', 'max': 10},
    'flavor': {'name': 'Flavor', 'max': 10},
    'sauce': {'name': 'Sauce', 'max': 10},
    'smoke': {'name': 'Smoke/Char', 'max': 10},
    'appearance': {'name': 'Appearance', 'max': 10}
}

RIB_SETS = ['Set A', 'Set B', 'Set C', 'Set D', 'Set E']

# Initialize session state
if 'scores' not in st.session_state:
    st.session_state.scores = []
if 'current_view' not in st.session_state:
    st.session_state.current_view = 'home'
if 'user_name' not in st.session_state:
    st.session_state.user_name = ''
if 'current_submission' not in st.session_state:
    st.session_state.current_submission = {i: {} for i in range(len(RIB_SETS))}

def save_submission(name, submission):
    """Save a user's scores"""
    entry = {
        'user_name': name,
        'timestamp': datetime.now().isoformat(),
        'scores': submission
    }
    st.session_state.scores.append(entry)

def calculate_averages():
    """Calculate average scores across all submissions"""
    if not st.session_state.scores:
        return None
    
    averages = {}
    for i, rib_set in enumerate(RIB_SETS):
        averages[rib_set] = {}
        for cat_id, cat_info in CATEGORIES.items():
            scores = [s['scores'][i].get(cat_id, 0) for s in st.session_state.scores 
                     if i in s['scores'] and cat_id in s['scores'][i]]
            averages[rib_set][cat_id] = sum(scores) / len(scores) if scores else 0
        averages[rib_set]['total'] = sum(averages[rib_set].values())
    
    return averages

def home_page():
    """Home page for entering name and starting"""
    st.title("🍖 Blind Rib Tasting")
    st.write("Rate 5 sets of ribs across multiple categories")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.write("")
        st.write("")
        name = st.text_input("Enter your name:", key="name_input", placeholder="Your name")
        
        col_a, col_b = st.columns(2)
        
        with col_a:
            if st.button("Start Tasting", type="primary", use_container_width=True, disabled=not name):
                st.session_state.user_name = name
                st.session_state.current_view = 'scoring'
                st.rerun()
        
        with col_b:
            if st.button("View Results", use_container_width=True):
                st.session_state.current_view = 'results'
                st.rerun()
        
        if st.session_state.scores:
            num_scores = len(st.session_state.scores)
            person_text = 'person has' if num_scores == 1 else 'people have'
            st.info(f"📊 {num_scores} {person_text} submitted scores")

def scoring_page():
    """Page for scoring ribs"""
    st.title(f"🍖 Scoring: {st.session_state.user_name}")
    
    # Rib set selector
    def format_rib_set(x):
        checkmark = '✓' if all(cat in st.session_state.current_submission[x] for cat in CATEGORIES.keys()) else ''
        return f"{RIB_SETS[x]} {checkmark}"
    
    rib_set_idx = st.radio(
        "Select Rib Set:",
        range(len(RIB_SETS)),
        format_func=format_rib_set,
        horizontal=True
    )
    
    st.write("---")
    st.subheader(RIB_SETS[rib_set_idx])
    
    # Score sliders for each category
    for cat_id, cat_info in CATEGORIES.items():
        current_score = st.session_state.current_submission[rib_set_idx].get(cat_id, 0)
        score = st.slider(
            f"{cat_info['name']}",
            min_value=0,
            max_value=cat_info['max'],
            value=current_score,
            key=f"score_{rib_set_idx}_{cat_id}"
        )
        st.session_state.current_submission[rib_set_idx][cat_id] = score
    
    st.write("---")
    
    # Navigation buttons
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        if st.button("← Back to Home"):
            st.session_state.current_view = 'home'
            st.rerun()
    
    with col3:
        # Check if all sets are complete
        all_complete = all(
            all(cat in st.session_state.current_submission[i] for cat in CATEGORIES.keys())
            for i in range(len(RIB_SETS))
        )
        
        if st.button("Submit All Scores", type="primary", disabled=not all_complete):
            save_submission(st.session_state.user_name, st.session_state.current_submission)
            st.session_state.current_submission = {i: {} for i in range(len(RIB_SETS))}
            st.session_state.current_view = 'results'
            st.success("Scores submitted successfully!")
            st.rerun()
    
    # Progress indicator
    completed = sum(1 for i in range(len(RIB_SETS)) 
                   if all(cat in st.session_state.current_submission[i] for cat in CATEGORIES.keys()))
    st.progress(completed / len(RIB_SETS))
    st.caption(f"Completed: {completed}/{len(RIB_SETS)} sets")

def results_page():
    """Page showing results and visualizations"""
    st.title("📊 Tasting Results")
    
    if st.button("← Back to Home"):
        st.session_state.current_view = 'home'
        st.rerun()
    
    if not st.session_state.scores:
        st.warning("No submissions yet! Be the first to rate the ribs.")
        return
    
    num_submissions = len(st.session_state.scores)
    submission_text = 'submission' if num_submissions == 1 else 'submissions'
    st.info(f"Based on {num_submissions} {submission_text}")
    
    averages = calculate_averages()
    
    # Overall Rankings
    st.subheader("🏆 Overall Rankings")
    rankings = sorted(
        [(name, data['total']) for name, data in averages.items()],
        key=lambda x: x[1],
        reverse=True
    )
    
    for rank, (rib_set, total) in enumerate(rankings, 1):
        medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"{rank}."
        st.metric(f"{medal} {rib_set}", f"{total:.1f}/50")
    
    st.write("---")
    
    # Category Breakdown Bar Chart
    st.subheader("📊 Category Breakdown")
    
    chart_data = []
    for rib_set, scores in averages.items():
        for cat_id, cat_info in CATEGORIES.items():
            chart_data.append({
                'Rib Set': rib_set,
                'Category': cat_info['name'],
                'Score': scores[cat_id]
            })
    
    df = pd.DataFrame(chart_data)
    fig = px.bar(df, x='Rib Set', y='Score', color='Category', 
                 barmode='group', height=400,
                 color_discrete_sequence=px.colors.sequential.Oranges_r)
    st.plotly_chart(fig, use_container_width=True)
    
    st.write("---")
    
    # Radar Charts
    st.subheader("🎯 Individual Rib Set Profiles")
    
    cols = st.columns(3)
    for idx, (rib_set, scores) in enumerate(averages.items()):
        with cols[idx % 3]:
            categories = [cat_info['name'] for cat_info in CATEGORIES.values()]
            values = [scores[cat_id] for cat_id in CATEGORIES.keys()]
            
            fig = go.Figure()
            fig.add_trace(go.Scatterpolar(
                r=values,
                theta=categories,
                fill='toself',
                name=rib_set
            ))
            
            fig.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0, 10])),
                showlegend=False,
                title=rib_set,
                height=300
            )
            st.plotly_chart(fig, use_container_width=True)
    
    st.write("---")
    
    # Individual Submissions
    with st.expander("View Individual Submissions"):
        for submission in st.session_state.scores:
            st.write(f"**{submission['user_name']}** - {submission['timestamp'][:10]}")
            
            submission_data = []
            for i, rib_set in enumerate(RIB_SETS):
                row = {'Rib Set': rib_set}
                for cat_id, cat_info in CATEGORIES.items():
                    row[cat_info['name']] = submission['scores'][i].get(cat_id, 0)
                submission_data.append(row)
            
            st.dataframe(pd.DataFrame(submission_data), use_container_width=True)
            st.write("---")

# Main app logic
def main():
    # Sidebar for admin/testing
    with st.sidebar:
        st.header("Admin Controls")
        if st.button("Reset All Data"):
            st.session_state.scores = []
            st.session_state.current_submission = {i: {} for i in range(len(RIB_SETS))}
            st.success("Data reset!")
            st.rerun()
        
        st.write("---")
        st.write("### Data Export")
        if st.session_state.scores:
            json_data = json.dumps(st.session_state.scores, indent=2)
            st.download_button(
                label="Download JSON",
                data=json_data,
                file_name="rib_tasting_scores.json",
                mime="application/json"
            )
    
    # Route to correct page
    if st.session_state.current_view == 'home':
        home_page()
    elif st.session_state.current_view == 'scoring':
        scoring_page()
    elif st.session_state.current_view == 'results':
        results_page()

if __name__ == "__main__":
    main()