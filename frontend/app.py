"""AI Governance Transparency Ledger - Streamlit Frontend."""

import requests
import streamlit as st
import streamlit.components.v1 as components
import secrets

API_BASE_URL = "http://localhost:8000"

# Initialize session state
if 'page' not in st.session_state:
    st.session_state.page = 'home'
if 'anon_id' not in st.session_state:
    st.session_state.anon_id = None
if 'first_visit' not in st.session_state:
    st.session_state.first_visit = True
if 'gate_result' not in st.session_state:
    st.session_state.gate_result = None

st.set_page_config(
    page_title="Transparency Ledger",
    page_icon="🔐",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Sync page state with query params (bidirectional)
query_page = st.query_params.get('page', None)
if query_page and query_page != st.session_state.page:
    # Query param changed (user clicked nav link) - update session state
    st.session_state.page = query_page
elif st.session_state.page != 'home':
    # Session state has a page - make sure query params match
    st.query_params['page'] = st.session_state.page

# AIGC-inspired Light Theme CSS with fixes
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

    :root {
        --color-bg: #ffffff;
        --color-bg-subtle: #f8f9fa;
        --color-text: #1d272a;
        --color-text-secondary: #52525b;
        --color-text-muted: #71717a;
        --color-border: #e5e7eb;
        --color-accent: #1d272a;
        --glow-golden: #f5c842;
        --glow-amber: #f8a035;
        --glow-peach: #ffb088;
        --glow-lavender: #c4a8ff;
        --color-critical: #dc2626;
        --color-high: #ea580c;
        --color-medium: #ca8a04;
        --color-good: #16a34a;
    }

    /* Base styles */
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
        background: var(--color-bg) !important;
    }

    /* Gradient glow orbs */
    .stApp::before {
        content: '';
        position: fixed;
        top: 5%;
        left: 50%;
        transform: translateX(-50%);
        width: 600px;
        height: 600px;
        background: radial-gradient(
            circle,
            rgba(245, 200, 66, 0.25) 0%,
            rgba(248, 160, 53, 0.15) 25%,
            rgba(255, 176, 136, 0.08) 50%,
            rgba(255, 255, 255, 0) 70%
        );
        border-radius: 50%;
        pointer-events: none;
        z-index: 0;
    }

    .stApp::after {
        content: '';
        position: fixed;
        top: 15%;
        right: 15%;
        width: 300px;
        height: 300px;
        background: radial-gradient(
            circle,
            rgba(196, 168, 255, 0.15) 0%,
            rgba(168, 212, 255, 0.1) 40%,
            rgba(255, 255, 255, 0) 70%
        );
        border-radius: 50%;
        pointer-events: none;
        z-index: 0;
    }

    #MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"],
    [data-testid="stStatusWidget"], [data-testid="collapsedControl"] {
        display: none;
    }

    .main .block-container {
        max-width: 900px;
        padding-top: 1rem;
        padding-bottom: 4rem;
        position: relative;
        z-index: 1;
    }

    * { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }

    /* Typography - with proper contrast */
    h1 {
        color: var(--color-text) !important;
        font-weight: 600 !important;
        font-size: 2.75rem !important;
        letter-spacing: -0.03em !important;
        line-height: 1.1 !important;
        margin-bottom: 1rem !important;
    }

    h2 {
        color: var(--color-text) !important;
        font-weight: 600 !important;
        font-size: 1.25rem !important;
        letter-spacing: -0.02em !important;
        margin-top: 2rem !important;
    }

    h3 {
        font-family: 'IBM Plex Mono', monospace !important;
        color: var(--color-text-muted) !important;
        font-weight: 500 !important;
        font-size: 0.75rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.1em !important;
    }

    p, span, label, li {
        color: var(--color-text-secondary) !important;
        line-height: 1.7 !important;
    }

    .stMarkdown p {
        color: var(--color-text-secondary) !important;
    }

    .stMarkdown strong {
        color: var(--color-text) !important;
    }

    /* Navigation */
    .nav-container {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 1.5rem 0;
        border-bottom: 1px solid var(--color-border);
        margin-bottom: 3rem;
        background: rgba(255, 255, 255, 0.8);
        backdrop-filter: blur(8px);
        -webkit-backdrop-filter: blur(8px);
        position: relative;
        z-index: 10;
    }

    .nav-brand {
        display: flex;
        align-items: center;
        gap: 0.75rem;
    }

    .nav-brand-short {
        font-size: 1rem;
        font-weight: 600;
        color: var(--color-text);
        letter-spacing: 0.02em;
    }

    .nav-brand-full {
        font-size: 0.75rem;
        font-weight: 500;
        color: var(--color-text-muted);
        padding-left: 0.75rem;
        border-left: 1px solid var(--color-border);
    }

    .nav-links {
        display: flex;
        gap: 2.5rem;
    }

    .nav-link {
        font-size: 0.9375rem;
        font-weight: 500;
        color: var(--color-text-secondary);
        text-decoration: none;
        transition: color 0.2s ease;
        position: relative;
        padding-bottom: 4px;
    }

    .nav-link:hover {
        color: var(--color-text);
    }

    .nav-link::after {
        content: '';
        position: absolute;
        bottom: 0;
        left: 0;
        width: 0;
        height: 2px;
        background: linear-gradient(90deg, var(--glow-golden), var(--glow-amber));
        transition: width 0.2s ease;
    }

    .nav-link:hover::after {
        width: 100%;
    }

    .nav-link.active {
        color: var(--color-text);
    }

    .nav-link.active::after {
        width: 100%;
    }

    /* Page header */
    .page-header {
        text-align: center;
        margin-bottom: 3rem;
    }

    .page-label {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.6875rem;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.15em;
        color: var(--color-text-muted);
        margin-bottom: 0.75rem;
    }

    .page-title {
        font-size: 2.75rem;
        font-weight: 600;
        color: var(--color-text);
        letter-spacing: -0.03em;
        line-height: 1.1;
        margin-bottom: 1rem;
    }

    .page-subtitle {
        font-size: 1.125rem;
        color: var(--color-text-secondary);
        max-width: 600px;
        margin: 0 auto;
        line-height: 1.7;
    }

    /* Hero section */
    .hero {
        text-align: center;
        padding: 2rem 0 3rem;
    }

    .hero-title {
        font-size: 3rem;
        font-weight: 600;
        color: var(--color-text);
        letter-spacing: -0.03em;
        line-height: 1.1;
        margin-bottom: 1.5rem;
    }

    .hero-subtitle {
        font-size: 1.125rem;
        color: var(--color-text-secondary);
        max-width: 580px;
        margin: 0 auto 2rem;
        line-height: 1.7;
    }

    .hero-note {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.8125rem;
        color: var(--color-text-muted);
        margin-top: 1rem;
    }

    /* Onboarding banner */
    .onboarding-banner {
        background: linear-gradient(135deg, rgba(245, 200, 66, 0.15), rgba(196, 168, 255, 0.1));
        border: 1px solid rgba(245, 200, 66, 0.3);
        border-radius: 12px;
        padding: 1.25rem 1.5rem;
        margin-bottom: 2rem;
        display: flex;
        align-items: center;
        gap: 1rem;
    }

    .onboarding-icon {
        font-size: 1.5rem;
    }

    .onboarding-text {
        flex: 1;
    }

    .onboarding-title {
        font-weight: 600;
        color: var(--color-text);
        margin-bottom: 0.25rem;
    }

    .onboarding-desc {
        font-size: 0.875rem;
        color: var(--color-text-secondary);
    }

    /* Forms */
    .stTextInput input, .stTextArea textarea {
        background: var(--color-bg) !important;
        border: 1.5px solid var(--color-border) !important;
        border-radius: 8px !important;
        color: var(--color-text) !important;
        font-size: 0.9375rem !important;
        padding: 0.75rem 1rem !important;
    }

    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: var(--color-accent) !important;
        box-shadow: 0 0 0 3px rgba(29, 39, 42, 0.08) !important;
    }

    .stTextInput input::placeholder, .stTextArea textarea::placeholder {
        color: var(--color-text-muted) !important;
    }

    .stTextInput label, .stTextArea label, .stSelectbox label {
        font-size: 0.8125rem !important;
        font-weight: 500 !important;
        color: var(--color-text) !important;
    }

    .stSelectbox > div > div {
        background: var(--color-bg) !important;
        border: 1.5px solid var(--color-border) !important;
        border-radius: 8px !important;
    }

    .stSelectbox [data-baseweb="select"] {
        color: var(--color-text) !important;
    }

    /* Helper text */
    .helper-text {
        font-size: 0.8125rem;
        color: var(--color-text-muted);
        margin-top: 0.25rem;
    }

    /* Buttons */
    .stButton button {
        border-radius: 9999px !important;
        font-weight: 500 !important;
        font-size: 0.9375rem !important;
        padding: 0.75rem 2rem !important;
        transition: all 0.2s ease !important;
    }

    .stButton button[kind="primary"] {
        background: var(--color-accent) !important;
        color: white !important;
        border: none !important;
    }

    .stButton button[kind="primary"]:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 20px rgba(29, 39, 42, 0.2) !important;
    }

    .stButton button[kind="secondary"] {
        background: transparent !important;
        color: var(--color-text) !important;
        border: 1.5px solid var(--color-border) !important;
    }

    .stButton button[kind="secondary"]:hover {
        border-color: var(--color-text) !important;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        background: transparent !important;
        gap: 0.5rem !important;
        border-bottom: 1px solid var(--color-border) !important;
    }

    .stTabs [data-baseweb="tab"] {
        color: var(--color-text-secondary) !important;
        background: transparent !important;
        padding: 0.75rem 1.25rem !important;
        font-weight: 500 !important;
        border-radius: 0 !important;
        border-bottom: 2px solid transparent !important;
    }

    .stTabs [aria-selected="true"] {
        color: var(--color-text) !important;
        border-bottom: 2px solid var(--glow-golden) !important;
        background: transparent !important;
    }

    /* Metrics */
    [data-testid="stMetricValue"] {
        color: var(--color-text) !important;
        font-size: 2.5rem !important;
        font-weight: 600 !important;
        letter-spacing: -0.03em !important;
    }

    [data-testid="stMetricLabel"] {
        font-family: 'IBM Plex Mono', monospace !important;
        color: var(--color-text-muted) !important;
        font-size: 0.6875rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.1em !important;
    }

    /* Forms container */
    [data-testid="stForm"] {
        background: var(--color-bg-subtle) !important;
        border: 1px solid var(--color-border) !important;
        border-radius: 12px !important;
        padding: 1.5rem !important;
    }

    /* Expander */
    .stExpander {
        background: var(--color-bg) !important;
        border: 1px solid var(--color-border) !important;
        border-radius: 8px !important;
    }

    .stExpander [data-testid="stExpanderToggleIcon"] {
        color: var(--color-text-muted) !important;
    }

    /* Divider */
    hr {
        border-color: var(--color-border) !important;
        margin: 2rem 0 !important;
    }

    /* Radio */
    .stRadio label {
        color: var(--color-text-secondary) !important;
    }

    .stRadio [data-baseweb="radio"] {
        background: var(--color-bg) !important;
    }

    /* Code blocks */
    code {
        font-family: 'IBM Plex Mono', monospace !important;
        background: var(--color-bg-subtle) !important;
        color: var(--color-text-secondary) !important;
        padding: 0.5rem 0.75rem !important;
        border-radius: 4px !important;
        font-size: 0.8125rem !important;
    }

    /* Alerts */
    .stAlert {
        border-radius: 8px !important;
    }

    /* Feature cards */
    .feature-card {
        padding: 1.5rem;
        background: var(--color-bg);
        border: 1px solid var(--color-border);
        border-radius: 12px;
        transition: all 0.2s ease;
        cursor: pointer;
        height: 100%;
    }

    .feature-card:hover {
        border-color: transparent;
        transform: translateY(-4px);
        background: linear-gradient(135deg, rgba(245, 200, 66, 0.1), rgba(196, 168, 255, 0.1));
        box-shadow: 0 8px 24px rgba(245, 200, 66, 0.15);
    }

    .feature-icon {
        font-size: 1.5rem;
        margin-bottom: 0.75rem;
    }

    .feature-title {
        font-weight: 600;
        font-size: 1rem;
        color: var(--color-text);
        margin-bottom: 0.5rem;
    }

    .feature-desc {
        font-size: 0.875rem;
        color: var(--color-text-secondary);
        line-height: 1.6;
    }

    /* Status badges */
    .status-badge {
        display: inline-block;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.6875rem;
        padding: 0.25rem 0.75rem;
        border-radius: 4px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-weight: 500;
        margin-right: 0.5rem;
    }

    .status-verified {
        background: rgba(22, 163, 74, 0.1);
        color: var(--color-good);
    }

    .status-submitted, .status-pending {
        background: rgba(245, 200, 66, 0.2);
        color: #92400e;
    }

    .status-rejected {
        background: rgba(220, 38, 38, 0.1);
        color: var(--color-critical);
    }

    .status-open {
        background: rgba(234, 88, 12, 0.1);
        color: var(--color-high);
    }

    .status-resolved, .status-addressed {
        background: rgba(22, 163, 74, 0.1);
        color: var(--color-good);
    }

    /* Caption */
    .stCaption {
        color: var(--color-text-muted) !important;
        font-size: 0.8125rem !important;
    }

    /* Mirror cards */
    .mirror-card {
        padding: 1.5rem;
        border-radius: 12px;
        text-align: center;
        margin-bottom: 1rem;
    }

    .mirror-card.consistent {
        background: linear-gradient(135deg, rgba(22, 163, 74, 0.05), rgba(22, 163, 74, 0.1));
        border: 1px solid rgba(22, 163, 74, 0.2);
    }

    .mirror-card.divergent {
        background: linear-gradient(135deg, rgba(220, 38, 38, 0.05), rgba(220, 38, 38, 0.1));
        border: 1px solid rgba(220, 38, 38, 0.2);
    }

    .mirror-title {
        font-weight: 600;
        font-size: 1rem;
        margin-bottom: 0.25rem;
    }

    .mirror-card.consistent .mirror-title {
        color: var(--color-good);
    }

    .mirror-card.divergent .mirror-title {
        color: var(--color-critical);
    }

    .mirror-status {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.6875rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
    }

    /* Empty state */
    .empty-state {
        text-align: center;
        padding: 3rem 2rem;
        background: var(--color-bg-subtle);
        border-radius: 12px;
        border: 1px dashed var(--color-border);
    }

    .empty-state-icon {
        font-size: 2.5rem;
        margin-bottom: 1rem;
        opacity: 0.5;
    }

    .empty-state-title {
        font-weight: 600;
        color: var(--color-text);
        margin-bottom: 0.5rem;
    }

    .empty-state-desc {
        font-size: 0.875rem;
        color: var(--color-text-muted);
    }

    /* Section header */
    .section-header {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin-bottom: 1rem;
    }

    .section-label {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.6875rem;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: var(--color-text-muted);
    }

    /* Inline help */
    .inline-help {
        font-size: 0.8125rem;
        color: var(--color-text-muted);
        background: var(--color-bg-subtle);
        padding: 0.75rem 1rem;
        border-radius: 8px;
        margin-bottom: 1rem;
        border-left: 3px solid var(--glow-golden);
    }

    /* Spinner override */
    .stSpinner > div {
        border-top-color: var(--glow-golden) !important;
    }

    /* Responsive */
    @media (max-width: 768px) {
        .nav-container {
            flex-direction: column;
            gap: 1rem;
            text-align: center;
        }

        .nav-links {
            gap: 1.5rem;
        }

        .hero-title, .page-title {
            font-size: 2rem;
        }

        .stApp::before, .stApp::after {
            display: none;
        }
    }
</style>
""", unsafe_allow_html=True)


def api_get(endpoint):
    """GET request to API with error handling."""
    try:
        resp = requests.get(f"{API_BASE_URL}{endpoint}", timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def api_post(endpoint, data=None):
    """POST request to API with error handling."""
    try:
        resp = requests.post(f"{API_BASE_URL}{endpoint}", json=data, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def render_page_header(label, title, subtitle=None):
    """Render a consistent page header."""
    subtitle_html = f'<div class="page-subtitle">{subtitle}</div>' if subtitle else ''
    st.markdown(f"""
    <div class="page-header">
        <div class="page-label">{label}</div>
        <div class="page-title">{title}</div>
        {subtitle_html}
    </div>
    """, unsafe_allow_html=True)


def render_empty_state(icon, title, description, action_text=None):
    """Render an empty state with guidance."""
    st.markdown(f"""
    <div class="empty-state">
        <div class="empty-state-icon">{icon}</div>
        <div class="empty-state-title">{title}</div>
        <div class="empty-state-desc">{description}</div>
    </div>
    """, unsafe_allow_html=True)


# Check API connection
api_status = api_get("/health")
if not api_status:
    st.error("Cannot connect to API. Start the server with: `python run.py`")
    st.stop()

# Navigation
current_page = st.session_state.page

st.markdown(f"""
<div class="nav-container">
    <div class="nav-brand">
        <span class="nav-brand-short">TRANSPARENCY LEDGER</span>
        <span class="nav-brand-full">AI Governance Infrastructure</span>
    </div>
    <div class="nav-links">
        <a href="?page=home" target="_self" class="nav-link {'active' if current_page == 'home' else ''}">Overview</a>
        <a href="?page=compliance" target="_self" class="nav-link {'active' if current_page == 'compliance' else ''}">Compliance</a>
        <a href="?page=concerns" target="_self" class="nav-link {'active' if current_page == 'concerns' else ''}">Concerns</a>
        <a href="?page=gate" target="_self" class="nav-link {'active' if current_page == 'gate' else ''}">Gate</a>
        <a href="?page=mirrors" target="_self" class="nav-link {'active' if current_page == 'mirrors' else ''}">Mirrors</a>
    </div>
</div>
""", unsafe_allow_html=True)


# ============================================================
# HOME PAGE
# ============================================================
if st.session_state.page == 'home':
    # Check if data exists
    stats = api_get("/transparency/stats") or {}
    submissions = api_get("/compliance/submissions") or []
    has_data = len(submissions) > 0

    # Onboarding banner for first-time users
    if not has_data:
        st.markdown("""
        <div class="onboarding-banner">
            <div class="onboarding-icon">👋</div>
            <div class="onboarding-text">
                <div class="onboarding-title">Welcome! Load demo data to explore</div>
                <div class="onboarding-desc">See how the transparency ledger works with sample compliance submissions, concerns, and multi-party mirrors.</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Hero section
    st.markdown("""
    <div class="hero">
        <div class="hero-title">Verify compliance without exposing secrets</div>
        <div class="hero-subtitle">
            A shared transparency ledger for AI governance where labs submit compliance documentation,
            anyone can raise concerns anonymously, and deployment is blocked until all requirements are met.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Submissions", len(submissions))
    col2.metric("Verified", stats.get('compliance_by_status', {}).get('verified', 0))
    col3.metric("Open Concerns", stats.get('concerns_by_status', {}).get('open', 0))
    col4.metric("Resolved", stats.get('concerns_by_status', {}).get('resolved', 0))

    st.divider()

    # Feature cards
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
        <div class="feature-card" onclick="window.location.href='?page=compliance'">
            <div class="feature-icon">🔗</div>
            <div class="feature-title">Hash Chain Integrity</div>
            <div class="feature-desc">Every record is cryptographically linked. Any modification breaks the chain and is immediately detectable.</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown("""
        <div class="feature-card" onclick="window.location.href='?page=gate'">
            <div class="feature-icon">🔒</div>
            <div class="feature-title">Zero-Knowledge Proofs</div>
            <div class="feature-desc">Prove compliance thresholds are met without revealing sensitive details like exact evaluation scores.</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown("""
        <div class="feature-card" onclick="window.location.href='?page=mirrors'">
            <div class="feature-icon">🪞</div>
            <div class="feature-title">Multi-Party Mirrors</div>
            <div class="feature-desc">Labs, auditors, and government each hold copies. No single party can tamper undetected.</div>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    # Action buttons
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Load demo data", use_container_width=True, type="primary" if not has_data else "secondary"):
            with st.spinner("Loading demo data..."):
                api_post("/demo/reset")
                api_post("/demo/transparency-reset")
                api_post("/demo/transparency-populate")
                api_post("/demo/compliance-populate")
                # Auto-sync mirrors so they're ready for the demo
                api_post("/demo/mirror/sync", {"include_concerns": True, "include_submissions": True})
            st.success("Demo data loaded and mirrors synced!")
            st.rerun()
    with col2:
        if st.button("Check deployment gate", use_container_width=True, type="secondary"):
            st.session_state.page = "gate"
            st.query_params["page"] = "gate"
            st.rerun()
    with col3:
        if st.button("View mirrors", use_container_width=True, type="secondary"):
            st.session_state.page = "mirrors"
            st.query_params["page"] = "mirrors"
            st.rerun()

    st.markdown('<p class="hero-note">No account required. All data is stored locally for this demo.</p>', unsafe_allow_html=True)


# ============================================================
# COMPLIANCE PAGE
# ============================================================
elif st.session_state.page == 'compliance':
    render_page_header(
        "Compliance",
        "Submit & Review Documentation",
        "Labs submit compliance evidence. Auditors verify and approve."
    )

    role = st.radio("I am a...", ["Lab (submit documentation)", "Auditor (review submissions)"], horizontal=True, key="compliance_role")
    is_lab = "Lab" in role

    st.divider()

    if is_lab:
        st.markdown('<div class="section-label">Submit New Documentation</div>', unsafe_allow_html=True)

        st.markdown("""
        <div class="inline-help">
            Submit compliance documentation for a model deployment. All fields are required.
            The evidence hash should be a SHA-256 hash of your supporting documents.
        </div>
        """, unsafe_allow_html=True)

        with st.form("submit_form"):
            col1, col2 = st.columns(2)
            with col1:
                template = st.selectbox(
                    "Template Type",
                    ["safety_evaluation", "capability_assessment", "red_team_report"],
                    help="The type of compliance documentation"
                )
                deployment_id = st.text_input(
                    "Deployment ID",
                    placeholder="e.g., gpt-safe-v2.1-prod"
                )
            with col2:
                model_id = st.text_input(
                    "Model ID",
                    placeholder="e.g., gpt-safe-v2.1"
                )
                evidence_hash = st.text_input(
                    "Evidence Hash",
                    placeholder="64-character SHA-256 hash",
                    help="SHA-256 hash of your evidence documents"
                )

            title = st.text_input("Title", placeholder="e.g., Safety Evaluation Report for GPT-Safe v2.1")
            summary = st.text_area("Summary", placeholder="Brief description of the evaluation findings...")

            submitted = st.form_submit_button("Submit Documentation", type="primary")
            if submitted:
                # Validation
                errors = []
                if not deployment_id:
                    errors.append("Deployment ID is required")
                if not model_id:
                    errors.append("Model ID is required")
                if not title:
                    errors.append("Title is required")
                if not summary:
                    errors.append("Summary is required")
                if not evidence_hash or len(evidence_hash) != 64:
                    errors.append("Evidence hash must be exactly 64 characters (SHA-256)")

                if errors:
                    for error in errors:
                        st.error(error)
                else:
                    with st.spinner("Submitting..."):
                        result = api_post(f"/compliance/submissions?lab_id=Anthropic", {
                            "template_type": template,
                            "deployment_id": deployment_id,
                            "model_id": model_id,
                            "title": title,
                            "summary": summary,
                            "evidence_hash": evidence_hash,
                            "metadata": {}
                        })
                    if result:
                        st.success("Documentation submitted successfully!")
                        st.rerun()
                    else:
                        st.error("Submission failed. Please try again.")

    else:
        st.markdown('<div class="section-label">Pending Reviews</div>', unsafe_allow_html=True)
        pending = api_get("/compliance/submissions?status=submitted") or []

        if not pending:
            render_empty_state(
                "✅",
                "No pending reviews",
                "All submissions have been reviewed. Check back later for new submissions."
            )
        else:
            for s in pending:
                st.markdown(f'<span class="status-badge status-pending">Pending</span> **{s["title"]}**', unsafe_allow_html=True)
                st.caption(f"{s['lab_id']} • {s['deployment_id']} • {s['template_type']}")

                with st.expander("Review this submission"):
                    st.markdown("**Evidence Hash:**")
                    st.code(s["evidence_hash"])

                    decision = st.radio(
                        "Decision",
                        ["verified", "rejected"],
                        key=f"decision_{s['id']}",
                        horizontal=True,
                        help="Verify if the evidence is valid and complete"
                    )
                    notes = st.text_area(
                        "Review Notes",
                        key=f"notes_{s['id']}",
                        placeholder="Explain your decision..."
                    )

                    if st.button("Submit Review", key=f"submit_{s['id']}", type="primary"):
                        if not notes or len(notes) < 5:
                            st.error("Please add review notes (at least 5 characters)")
                        else:
                            with st.spinner("Submitting review..."):
                                result = api_post(f"/compliance/review?auditor_id=AI Safety Institute", {
                                    "submission_id": s['id'],
                                    "status": decision,
                                    "notes": notes,
                                    "evidence_verified": True
                                })
                            if result:
                                st.success("Review submitted!")
                                st.rerun()
                            else:
                                st.error("Failed to submit review")

    st.divider()
    st.markdown('<div class="section-label">All Submissions</div>', unsafe_allow_html=True)

    all_submissions = api_get("/compliance/submissions") or []
    if not all_submissions:
        render_empty_state(
            "📄",
            "No submissions yet",
            "Load demo data from the Overview page, or submit new documentation above."
        )
    else:
        for s in all_submissions:
            status_class = {"submitted": "status-submitted", "verified": "status-verified", "rejected": "status-rejected"}.get(s['status'], "status-pending")
            st.markdown(f'<span class="status-badge {status_class}">{s["status"]}</span> **{s["title"]}**', unsafe_allow_html=True)
            st.caption(f"{s['template_type']} • {s['lab_id']} • {s['deployment_id']}")
            st.markdown("")


# ============================================================
# CONCERNS PAGE
# ============================================================
elif st.session_state.page == 'concerns':
    render_page_header(
        "Concerns",
        "Anonymous Whistleblower Submissions",
        "Raise safety concerns anonymously. Your identity is protected through client-side hashing."
    )

    tab1, tab2 = st.tabs(["Submit a Concern", "View All Concerns"])

    with tab1:
        if not st.session_state.anon_id:
            st.markdown('<div class="section-label">Step 1: Generate Anonymous ID</div>', unsafe_allow_html=True)

            st.markdown("""
            <div class="inline-help">
                Your anonymous ID is generated locally in your browser using SHA-256 hashing.
                Your email and passphrase never leave your device.
            </div>
            """, unsafe_allow_html=True)

            col1, col2 = st.columns([2, 1])
            with col1:
                components.html("""
                <div style="font-family: Inter, -apple-system, sans-serif; padding: 1.5rem; background: #f8f9fa; border: 1px solid #e5e7eb; border-radius: 12px;">
                    <div style="margin-bottom: 1rem;">
                        <label style="display: block; font-size: 13px; font-weight: 500; color: #1d272a; margin-bottom: 4px;">Email or Identity</label>
                        <input type="text" id="identity" placeholder="you@company.com" style="width: 100%; padding: 10px 12px; background: #ffffff; border: 1.5px solid #e5e7eb; border-radius: 8px; color: #1d272a; font-size: 14px; font-family: inherit; box-sizing: border-box;">
                    </div>
                    <div style="margin-bottom: 1rem;">
                        <label style="display: block; font-size: 13px; font-weight: 500; color: #1d272a; margin-bottom: 4px;">Secret Passphrase</label>
                        <input type="password" id="salt" placeholder="At least 8 characters" style="width: 100%; padding: 10px 12px; background: #ffffff; border: 1.5px solid #e5e7eb; border-radius: 8px; color: #1d272a; font-size: 14px; font-family: inherit; box-sizing: border-box;">
                    </div>
                    <button onclick="gen()" style="background: #1d272a; color: white; border: none; padding: 10px 24px; border-radius: 9999px; cursor: pointer; font-weight: 500; font-size: 14px; font-family: inherit;">Generate ID</button>
                    <div id="out" style="display: none; margin-top: 1rem; padding: 1rem; background: rgba(22, 163, 74, 0.08); border: 1px solid rgba(22, 163, 74, 0.2); border-radius: 8px;">
                        <div style="font-size: 12px; color: #16a34a; margin-bottom: 6px; font-weight: 500;">Your Anonymous ID:</div>
                        <input type="text" id="result" readonly onclick="this.select(); document.execCommand('copy');" style="width: 100%; padding: 8px 10px; background: #ffffff; border: 1px solid #e5e7eb; border-radius: 4px; color: #16a34a; font-family: 'IBM Plex Mono', monospace; font-size: 14px; cursor: pointer; box-sizing: border-box;">
                        <div style="font-size: 11px; color: #71717a; margin-top: 6px;">Click to copy, then paste below</div>
                    </div>
                </div>
                <script>
                async function gen() {
                    const id = document.getElementById('identity').value;
                    const salt = document.getElementById('salt').value;
                    if (!id) { alert('Please enter your email or identity'); return; }
                    if (salt.length < 8) { alert('Passphrase must be at least 8 characters'); return; }
                    const data = new TextEncoder().encode(id + '||' + salt);
                    const hash = await crypto.subtle.digest('SHA-256', data);
                    const hex = Array.from(new Uint8Array(hash)).map(b => b.toString(16).padStart(2, '0')).join('');
                    document.getElementById('result').value = 'anon_' + hex.substring(0, 12);
                    document.getElementById('out').style.display = 'block';
                }
                </script>
                """, height=300)

            st.markdown("")
            st.markdown('<div class="section-label">Step 2: Paste Your Anonymous ID</div>', unsafe_allow_html=True)
            anon_input = st.text_input("Anonymous ID", placeholder="anon_xxxxxxxxxxxx", key="anon_input", label_visibility="collapsed")

            if st.button("Continue with this ID", type="primary"):
                if anon_input and anon_input.startswith("anon_") and len(anon_input) == 17:
                    st.session_state.anon_id = anon_input
                    st.rerun()
                else:
                    st.error("Invalid format. ID should be 'anon_' followed by 12 characters.")

        else:
            st.success(f"Using Anonymous ID: `{st.session_state.anon_id}`")

            st.markdown('<div class="section-label">Submit Your Concern</div>', unsafe_allow_html=True)

            with st.form("concern_form"):
                category = st.selectbox(
                    "Category",
                    ["safety_eval", "capability_risk", "deployment", "other"],
                    help="What type of concern is this?"
                )
                title = st.text_input("Title", placeholder="Brief summary of the concern")
                description = st.text_area(
                    "Description",
                    placeholder="Provide details about your concern...",
                    height=150
                )

                col1, col2 = st.columns([1, 3])
                with col1:
                    if st.form_submit_button("Submit Anonymously", type="primary"):
                        if not title:
                            st.error("Please enter a title")
                        elif not description:
                            st.error("Please enter a description")
                        else:
                            with st.spinner("Submitting..."):
                                result = api_post(
                                    f"/transparency/concerns?submitter_id={st.session_state.anon_id}&role=whistleblower",
                                    {"category": category, "title": title, "description": description}
                                )
                            if result:
                                st.success("Concern submitted anonymously!")
                                st.rerun()
                            else:
                                st.error("Submission failed")

            if st.button("Use a different ID", type="secondary"):
                st.session_state.anon_id = None
                st.rerun()

    with tab2:
        view_role = st.radio("View as", ["Public Viewer", "Lab (respond)", "Auditor (resolve)"], horizontal=True, key="view_role")

        concerns = api_get("/transparency/concerns") or []

        if not concerns:
            render_empty_state(
                "💬",
                "No concerns submitted yet",
                "Concerns will appear here once submitted. Load demo data to see examples."
            )
        else:
            for c in concerns:
                status_class = {
                    "open": "status-open",
                    "addressed": "status-addressed",
                    "resolved": "status-resolved",
                    "disputed": "status-rejected"
                }.get(c['status'], "status-pending")

                st.markdown(f'<span class="status-badge {status_class}">{c["status"]}</span> **{c["title"]}**', unsafe_allow_html=True)
                st.caption(f"{c['category']} • Submitted by {c['submitter_id'][:17]}")

                desc = c['description']
                st.markdown(desc[:200] + "..." if len(desc) > 200 else desc)

                if "Lab" in view_role and c['status'] == 'open':
                    with st.expander("Respond to this concern"):
                        response = st.text_area("Your response", key=f"resp_{c['id']}", placeholder="Address the concern...")
                        if st.button("Send Response", key=f"send_{c['id']}", type="primary"):
                            if response:
                                with st.spinner("Sending..."):
                                    api_post(f"/transparency/responses?responder_id=Lab&role=lab", {"concern_id": c['id'], "response_text": response})
                                st.success("Response sent!")
                                st.rerun()
                            else:
                                st.error("Please enter a response")

                if "Auditor" in view_role and c['status'] == 'addressed':
                    with st.expander("Resolve this concern"):
                        resolution = st.text_area("Resolution notes", key=f"res_{c['id']}", placeholder="Explain the resolution...")
                        if st.button("Mark as Resolved", key=f"resolve_{c['id']}", type="primary"):
                            if resolution:
                                with st.spinner("Resolving..."):
                                    api_post(f"/transparency/resolutions?auditor_id=Auditor", {"concern_id": c['id'], "resolution_notes": resolution})
                                st.success("Concern resolved!")
                                st.rerun()
                            else:
                                st.error("Please enter resolution notes")

                st.divider()


# ============================================================
# GATE PAGE
# ============================================================
elif st.session_state.page == 'gate':
    render_page_header(
        "Deployment Gate",
        "Check Release Authorization",
        "Verify if a model deployment is cleared for release based on compliance requirements."
    )

    # Input fields (not in a form)
    col1, col2 = st.columns(2)
    with col1:
        deployment_id = st.text_input(
            "Deployment ID",
            value="gpt-safe-v2.1-prod",
            key="gate_deployment_id"
        )
    with col2:
        model_id = st.text_input(
            "Model ID",
            value="gpt-safe-v2.1",
            key="gate_model_id"
        )

    # Check button and results in one container
    if st.button("Check Status", type="primary", key="gate_check"):
        if deployment_id and model_id:
            result = api_get(f"/compliance/status/{deployment_id}?model_id={model_id}")
            if result:
                st.divider()

                if result.get('is_cleared'):
                    st.success("✅ CLEARED FOR DEPLOYMENT - All requirements met, no blocking concerns")
                else:
                    st.error(f"🚫 BLOCKED - {result.get('message', 'Requirements not met')}")

                col1, col2 = st.columns(2)

                with col1:
                    st.subheader("Compliance Requirements")
                    for t in result.get('required_templates', []):
                        if t in result.get('verified_templates', []):
                            st.write(f"✅ {t.replace('_', ' ').title()}")
                        else:
                            st.write(f"❌ {t.replace('_', ' ').title()}")

                with col2:
                    st.subheader("Concerns Status")
                    st.metric("Open Concerns", result.get('open_concerns', 0))
                    st.metric("Resolved Concerns", result.get('resolved_concerns', 0))
            else:
                st.error("Failed to fetch status. Make sure demo data is loaded.")
        else:
            st.error("Please enter both Deployment ID and Model ID")


# ============================================================
# MIRRORS PAGE
# ============================================================
elif st.session_state.page == 'mirrors':
    render_page_header(
        "Multi-Party Mirrors",
        "Distributed Ledger Verification",
        "The ledger is replicated across labs, auditors, and government. Any tampering is immediately detectable."
    )

    st.markdown("""
    <div class="inline-help">
        Each party maintains their own copy of the ledger. Hashes are compared to detect any unauthorized modifications.
        If one party's data differs, tampering has occurred.
    </div>
    """, unsafe_allow_html=True)

    # Action buttons
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Sync All Mirrors", use_container_width=True, type="primary"):
            with st.spinner("Syncing mirrors..."):
                result = api_post("/demo/mirror/sync", {"include_concerns": True, "include_submissions": True})
            if result and not result.get('error'):
                st.success(f"Synced {result.get('record_count', 0)} records to all parties")
                st.rerun()
            else:
                st.error("Sync failed")

    with col2:
        if st.button("Detect Tampering", use_container_width=True):
            with st.spinner("Comparing hashes..."):
                detection = api_get("/demo/mirror/detect")
            if detection:
                if detection.get('tampering_detected'):
                    st.error("⚠️ Tampering detected!")
                else:
                    st.success("✅ No tampering detected")
            else:
                st.error("Detection failed")

    with col3:
        if st.button("Reset Mirrors", use_container_width=True, type="secondary"):
            with st.spinner("Resetting..."):
                api_post("/demo/mirror/reset")
            st.rerun()

    st.divider()

    # Mirror status cards
    mirrors = api_get("/demo/mirror/status") or []
    comparison = api_get("/demo/mirror/compare") or {}
    divergent_parties = [p.lower() for p in comparison.get('divergent_parties', [])]

    st.markdown('<div class="section-label">Mirror Status</div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    party_info = [
        ("Lab", "🏢", "AI development laboratory"),
        ("Auditor", "🔍", "Independent safety auditor"),
        ("Government", "🏛️", "Regulatory authority")
    ]

    for i, (col, (name, icon, desc)) in enumerate(zip([col1, col2, col3], party_info)):
        with col:
            mirror = mirrors[i] if len(mirrors) > i else {}
            is_divergent = name.lower() in divergent_parties

            card_class = "divergent" if is_divergent else "consistent"
            status_text = "DIVERGENT" if is_divergent else "Consistent"
            status_color = "#dc2626" if is_divergent else "#16a34a"

            st.markdown(f"""
            <div class="mirror-card {card_class}">
                <div style="font-size: 1.5rem; margin-bottom: 0.5rem;">{icon}</div>
                <div class="mirror-title">{name}</div>
                <div class="mirror-status" style="color: {status_color};">{status_text}</div>
            </div>
            """, unsafe_allow_html=True)

            st.metric("Records", mirror.get('record_count', 0))

            hash_val = mirror.get('hash', None)
            if hash_val:
                st.code(hash_val[:32] + "...", language=None)
            else:
                st.caption("No data synced")

    st.divider()

    # Overall status
    if comparison.get('all_consistent'):
        st.success("✅ All mirrors are consistent — no tampering detected")
    elif comparison.get('divergent_parties'):
        st.error(f"⚠️ Divergence detected in: {', '.join(comparison['divergent_parties'])}")
    else:
        st.info("Sync mirrors to begin comparison")

    st.divider()

    # Tampering simulation (in expander for demo purposes)
    with st.expander("🧪 Demo: Simulate Tampering"):
        st.markdown("""
        <div class="inline-help" style="border-left-color: #ea580c;">
            This is a demonstration feature. In a real system, tampering would require compromising a party's infrastructure.
        </div>
        """, unsafe_allow_html=True)

        with st.form("tamper_form"):
            col1, col2 = st.columns(2)

            with col1:
                target_party = st.selectbox(
                    "Target Party",
                    ["lab", "auditor", "government"],
                    help="Which party's mirror to tamper with"
                )
                record_id = st.text_input(
                    "Record ID",
                    placeholder="e.g., concern_001",
                    help="ID of the record to modify"
                )

            with col2:
                new_title = st.text_input(
                    "New Title (tampered value)",
                    placeholder="Fake title...",
                    help="The falsified value"
                )

            st.warning("⚠️ This will modify data in one party's mirror, causing divergence.")

            if st.form_submit_button("Tamper Record"):
                if not record_id or not new_title:
                    st.error("Enter both record ID and new title")
                else:
                    with st.spinner("Tampering..."):
                        result = api_post("/demo/mirror/tamper", {
                            "party": target_party,
                            "record_id": record_id,
                            "new_value": {"title": new_title, "tampered": True}
                        })
                    if result and not result.get('error'):
                        st.warning(f"Tampered {target_party}'s copy. Click 'Detect Tampering' to verify.")
                        st.rerun()
                    else:
                        st.error("Tamper failed — check that the record ID exists")
