import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Page config
st.set_page_config(page_title="Blind Rib Tasting", page_icon="🍖", layout="wide")

# Categories and rib sets
CATEGORIES = {
    'tenderness': {'name': 'Tenderness', 'max': 5},
    'flavor_sauce': {'name': 'Flavor / Sauce', 'max': 5},
    'smoke_char': {'name': 'Smoke / Char / Base Rub', 'max': 5},
    'overall': {'name': 'Overall Taste', 'max': 5}
}

RIB_SETS = ['Set A', 'Set B', 'Set C', 'Set D', 'Set E', 'Set F']

# Initialize session state
if 'scores' not in st.session_state:
    st.session_state.scores = []
if 'current_view' not in st.session_state:
    st.session_state.current_view = 'home'
if 'user_name' not in st.session_state:
    st.session_state.user_name = ''
if 'current_submission' not in st.session_state:
    st.session_state.current_submission = {i: {} for i in range(len(RIB_SETS))}
if 'selected_rib_set' not in st.session_state:
    st.session_state.selected_rib_set = 0
if 'sheets_service' not in st.session_state:
    st.session_state.sheets_service = None
if 'spreadsheet_id' not in st.session_state:
    st.session_state.spreadsheet_id = None

# Google Sheets Setup
def get_sheets_service():
    """Initialize Google Sheets API service"""
    try:
        credentials = service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        service = build('sheets', 'v4', credentials=credentials)
        return service
    except Exception as e:
        st.error(f"Error connecting to Google Sheets: {e}")
        return None

def init_spreadsheet():
    """Initialize or get spreadsheet ID"""
    if 'spreadsheet_id' in st.secrets:
        return st.secrets['spreadsheet_id']
    return None

def calculate_total(scores_dict):
    """Calculate total score (multiply each by 5, then sum for 20-100 scale)"""
    return sum(scores_dict.get(cat_id, 0) * 5 for cat_id in CATEGORIES.keys())

def save_to_sheets(service, spreadsheet_id, submission):
    """Save submission to Google Sheets"""
    try:
        # Prepare row data
        timestamp = submission['timestamp']
        user_name = submission['user_name']
        
        for set_idx, rib_set in enumerate(RIB_SETS):
            row = [timestamp, user_name, rib_set]
            for cat_id in CATEGORIES.keys():
                score = submission['scores'][set_idx].get(cat_id, 0)
                row.append(score)
            
            # Calculate total for this set (each score * 5)
            total = calculate_total(submission['scores'][set_idx])
            row.append(total)
            
            # Append to sheet
            body = {'values': [row]}
            service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range='Scores!A:H',
                valueInputOption='RAW',
                body=body
            ).execute()
        
        return True
    except HttpError as e:
        st.error(f"Error saving to sheets: {e}")
        return False

def load_from_sheets(service, spreadsheet_id):
    """Load all scores from Google Sheets"""
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range='Scores!A2:H'
        ).execute()
        
        values = result.get('values', [])
        if not values:
            return []
        
        # Convert to structured format
        submissions = {}
        for row in values:
            if len(row) < 8:
                continue
            
            timestamp = row[0]
            user_name = row[1]
            rib_set = row[2]
            scores = {
                list(CATEGORIES.keys())[i]: int(row[3 + i]) 
                for i in range(len(CATEGORIES))
            }
            
            key = f"{user_name}_{timestamp}"
            if key not in submissions:
                submissions[key] = {
                    'user_name': user_name,
                    'timestamp': timestamp,
                    'scores': {}
                }
            
            set_idx = RIB_SETS.index(rib_set)
            submissions[key]['scores'][set_idx] = scores
        
        return list(submissions.values())
    except HttpError as e:
        st.error(f"Error loading from sheets: {e}")
        return []

def clear_sheets_data(service, spreadsheet_id):
    """Clear all data from the Scores sheet (except header)"""
    try:
        service.spreadsheets().values().clear(
            spreadsheetId=spreadsheet_id,
            range='Scores!A2:I'
        ).execute()
        return True
    except HttpError as e:
        st.error(f"Error clearing sheets: {e}")
        return False

def ensure_sheet_structure(service, spreadsheet_id):
    """Ensure the spreadsheet has the correct structure"""
    try:
        # Check if Scores sheet exists
        spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        sheets = spreadsheet.get('sheets', [])
        
        scores_sheet_exists = any(sheet['properties']['title'] == 'Scores' for sheet in sheets)
        
        if not scores_sheet_exists:
            # Create Scores sheet
            body = {
                'requests': [{
                    'addSheet': {
                        'properties': {
                            'title': 'Scores'
                        }
                    }
                }]
            }
            service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body=body
            ).execute()
        
        # Add header row if sheet is empty
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range='Scores!A1:H1'
        ).execute()
        
        if not result.get('values'):
            header = ['Timestamp', 'User Name', 'Rib Set', 
                     'Tenderness', 'Flavor/Sauce', 'Smoke/Char/Rub', 'Overall Taste', 'Total']
            body = {'values': [header]}
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range='Scores!A1:H1',
                valueInputOption='RAW',
                body=body
            ).execute()
        
        return True
    except HttpError as e:
        st.error(f"Error setting up sheet structure: {e}")
        return False

def save_submission(name, submission):
    """Save a user's scores to session state and Google Sheets"""
    entry = {
        'user_name': name,
        'timestamp': datetime.now().isoformat(),
        'scores': submission
    }
    st.session_state.scores.append(entry)
    
    # Save to Google Sheets if connected
    if st.session_state.sheets_service and st.session_state.spreadsheet_id:
        save_to_sheets(st.session_state.sheets_service, st.session_state.spreadsheet_id, entry)

def calculate_averages(scores_list):
    """Calculate average scores across all submissions"""
    if not scores_list:
        return None
    
    averages = {}
    for i, rib_set in enumerate(RIB_SETS):
        averages[rib_set] = {}
        for cat_id, cat_info in CATEGORIES.items():
            scores = [s['scores'][i].get(cat_id, 0) for s in scores_list 
                     if i in s['scores'] and cat_id in s['scores'][i]]
            averages[rib_set][cat_id] = sum(scores) / len(scores) if scores else 0
        averages[rib_set]['total'] = calculate_total(averages[rib_set])
    
    return averages

def home_page():
    """Home page for entering name and starting"""
    st.title("🍖 Blind Rib Tasting")
    st.write("Rate 6 sets of ribs across 4 categories (1-5 scale, total score: 25-100)")
    
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
        
        # Show current session scores
        if st.session_state.scores:
            num_scores = len(st.session_state.scores)
            person_text = 'person has' if num_scores == 1 else 'people have'
            st.info(f"📊 Current session: {num_scores} {person_text} submitted scores")
        
        st.write("---")
        
        # Cumulative database button
        if st.button("📈 View Cumulative Database", use_container_width=True):
            st.session_state.current_view = 'cumulative'
            st.rerun()

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
        horizontal=True,
        index=st.session_state.selected_rib_set,
        key='rib_set_radio'
    )
    
    # Update session state when radio changes
    st.session_state.selected_rib_set = rib_set_idx
    
    st.write("---")
    st.subheader(RIB_SETS[rib_set_idx])
    
    # Score sliders for each category
    for cat_id, cat_info in CATEGORIES.items():
        current_score = st.session_state.current_submission[rib_set_idx].get(cat_id, 0)
        score = st.slider(
            f"{cat_info['name']}",
            min_value=1,
            max_value=cat_info['max'],
            value=current_score if current_score > 0 else 3,
            key=f"score_{rib_set_idx}_{cat_id}"
        )
        st.session_state.current_submission[rib_set_idx][cat_id] = score
    
    # Show current total for this set
    current_total = calculate_total(st.session_state.current_submission[rib_set_idx])
    st.metric("Current Total", f"{current_total}/100")
    
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
    st.title("📊 Current Session Results")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("← Back to Home"):
            st.session_state.current_view = 'home'
            st.rerun()
    with col2:
        if st.button("📈 View Cumulative Database"):
            st.session_state.current_view = 'cumulative'
            st.rerun()
    
    if not st.session_state.scores:
        st.warning("No submissions yet! Be the first to rate the ribs.")
        return
    
    num_submissions = len(st.session_state.scores)
    submission_text = 'submission' if num_submissions == 1 else 'submissions'
    st.info(f"Based on {num_submissions} {submission_text} in this session")
    
    averages = calculate_averages(st.session_state.scores)
    
    # Overall Rankings
    st.subheader("🏆 Overall Rankings")
    rankings = sorted(
        [(name, data['total']) for name, data in averages.items()],
        key=lambda x: x[1],
        reverse=True
    )
    
    for rank, (rib_set, total) in enumerate(rankings, 1):
        medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"{rank}."
        st.metric(f"{medal} {rib_set}", f"{total:.1f}/100")
    
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
    fig.update_yaxes(range=[0, 5])
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
                polar=dict(radialaxis=dict(visible=True, range=[0, 5])),
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
                row['Total'] = calculate_total(submission['scores'][i])
                submission_data.append(row)
            
            st.dataframe(pd.DataFrame(submission_data), use_container_width=True)
            st.write("---")

def cumulative_page():
    """Page showing cumulative database results"""
    st.title("📈 Cumulative Database Results")
    
    if st.button("← Back to Home"):
        st.session_state.current_view = 'home'
        st.rerun()
    
    # Load data from Google Sheets
    if st.session_state.sheets_service and st.session_state.spreadsheet_id:
        with st.spinner("Loading data from Google Sheets..."):
            all_scores = load_from_sheets(st.session_state.sheets_service, st.session_state.spreadsheet_id)
        
        if not all_scores:
            st.warning("No cumulative data found in the database.")
            return
        
        num_submissions = len(all_scores)
        submission_text = 'submission' if num_submissions == 1 else 'submissions'
        st.info(f"📊 All-time database: {num_submissions} {submission_text}")
        
        averages = calculate_averages(all_scores)
        
        # Overall Rankings
        st.subheader("🏆 All-Time Rankings")
        rankings = sorted(
            [(name, data['total']) for name, data in averages.items()],
            key=lambda x: x[1],
            reverse=True
        )
        
        for rank, (rib_set, total) in enumerate(rankings, 1):
            medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"{rank}."
            st.metric(f"{medal} {rib_set}", f"{total:.1f}/100")
        
        st.write("---")
        
        # Category Breakdown Bar Chart
        st.subheader("📊 Category Breakdown (All-Time)")
        
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
        fig.update_yaxes(range=[0, 5])
        st.plotly_chart(fig, use_container_width=True)
        
        st.write("---")
        
        # Radar Charts
        st.subheader("🎯 All-Time Rib Set Profiles")
        
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
                    polar=dict(radialaxis=dict(visible=True, range=[0, 5])),
                    showlegend=False,
                    title=rib_set,
                    height=300
                )
                st.plotly_chart(fig, use_container_width=True)
        
        st.write("---")
        
        # Admin controls for database
        st.subheader("⚙️ Database Management")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🗑️ Clear All Database Data", type="secondary"):
                if clear_sheets_data(st.session_state.sheets_service, st.session_state.spreadsheet_id):
                    st.success("Database cleared successfully!")
                    st.rerun()
        
        with col2:
            if st.button("🔄 Refresh Data"):
                st.rerun()
        
        # Show all submissions
        with st.expander("View All Submissions"):
            for submission in all_scores:
                st.write(f"**{submission['user_name']}** - {submission['timestamp'][:10]}")
                
                submission_data = []
                for i, rib_set in enumerate(RIB_SETS):
                    row = {'Rib Set': rib_set}
                    for cat_id, cat_info in CATEGORIES.items():
                        row[cat_info['name']] = submission['scores'][i].get(cat_id, 0)
                    row['Total'] = calculate_total(submission['scores'][i])
                    submission_data.append(row)
                
                st.dataframe(pd.DataFrame(submission_data), use_container_width=True)
                st.write("---")
    else:
        st.error("Google Sheets not configured. Please set up the connection in secrets.")

# Main app logic
def main():
    # Initialize Google Sheets connection
    if st.session_state.sheets_service is None:
        st.session_state.sheets_service = get_sheets_service()
        st.session_state.spreadsheet_id = init_spreadsheet()
        
        if st.session_state.sheets_service and st.session_state.spreadsheet_id:
            ensure_sheet_structure(st.session_state.sheets_service, st.session_state.spreadsheet_id)
    
    # Sidebar for admin/testing
    with st.sidebar:
        st.header("Admin Controls")
        
        # Connection status
        if st.session_state.sheets_service and st.session_state.spreadsheet_id:
            st.success("✅ Connected to Google Sheets")
        else:
            st.warning("⚠️ Google Sheets not configured")
        
        if st.button("Reset Session Data"):
            st.session_state.scores = []
            st.session_state.current_submission = {i: {} for i in range(len(RIB_SETS))}
            st.success("Session data reset!")
            st.rerun()
        
        st.write("---")
        st.write("### Session Data Export")
        if st.session_state.scores:
            json_data = json.dumps(st.session_state.scores, indent=2)
            st.download_button(
                label="Download Session JSON",
                data=json_data,
                file_name="rib_tasting_session.json",
                mime="application/json"
            )
    
    # Route to correct page
    if st.session_state.current_view == 'home':
        home_page()
    elif st.session_state.current_view == 'scoring':
        scoring_page()
    elif st.session_state.current_view == 'results':
        results_page()
    elif st.session_state.current_view == 'cumulative':
        cumulative_page()

if __name__ == "__main__":
    main()
