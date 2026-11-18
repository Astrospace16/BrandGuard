import streamlit as st
from PIL import Image
import json, os, re, uuid
from datetime import datetime

st.set_page_config(page_title="BrandGuard", page_icon="🛡️", layout="wide")

DATA_FILE = "brandguard_data.json"
DEFAULT_DATA = {
    "brand_name": "Antyrix Demo Brand",
    "colors": ["#2454A6", "#F1E8D0", "#111111"],
    "tone_words": ["clear", "confident", "helpful"],
    "avoid_words": ["revolutionary", "guarantee", "best in the world", "unbelievable"],
    "facts": [
        {"claim": "Founded in 2020", "source": "Approved company fact sheet"},
        {"claim": "Serving customers in 12 countries", "source": "Q3 company report"},
        {"claim": "24/7 customer support", "source": "Support policy v2"}
    ],
    "reviews": []
}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)

def load_data():
    if not os.path.exists(DATA_FILE):
        save_data(DEFAULT_DATA)
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            loaded = json.load(file)
        for key, value in DEFAULT_DATA.items():
            loaded.setdefault(key, value)
        return loaded
    except (json.JSONDecodeError, OSError):
        return DEFAULT_DATA.copy()

def fact_is_supported(claim, text):
    """Small demo matcher for the sample approved facts; not truth verification."""
    c = claim.lower()
    t = text.lower()
    if "founded in 2020" in c:
        return bool(re.search(r"\bfounded\s+in\s+2020\b", t))
    if "12 countries" in c:
        return bool(re.search(r"\b12\s+countries\b", t))
    if "24/7" in c and "customer support" in c:
        return bool(re.search(r"\b24\s*/\s*7\b", t) and "customer support" in t)
    return c in t

def scan_text(text, data):
    findings = []
    approved_spans = []

    for fact in data["facts"]:
        if fact_is_supported(fact["claim"], text):
            findings.append({
                "severity": "PASS",
                "rule": "Approved fact recognized",
                "detail": f"Matched approved fact: “{fact['claim']}”.",
                "source": fact["source"]
            })
            if "2020" in fact["claim"]:
                approved_spans.append("2020")
            if "12 countries" in fact["claim"]:
                approved_spans.extend(["12 countries", "12"])
            if "24/7" in fact["claim"]:
                approved_spans.extend(["24/7", "24", "7"])

    # Detect common numeric/statistical claim patterns.
    patterns = [
        r"\b\d+(?:\.\d+)?\s*%",
        r"\b\d+(?:\.\d+)?\s*(?:million|billion|thousand)\s+(?:users|customers|people|downloads| rupees|dollars)?",
        r"\b\d+(?:\.\d+)?\s+(?:users|customers|countries|years|employees)\b"
    ]
    candidates = []
    for pattern in patterns:
        candidates.extend(re.findall(pattern, text, flags=re.IGNORECASE))
    seen = set()
    for candidate in candidates:
        normalized = candidate.strip().lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        if any(normalized in approved.lower() or approved.lower() in normalized for approved in approved_spans):
            continue
        findings.append({
            "severity": "REVIEW",
            "rule": "Unverified number / statistic",
            "detail": f"Found “{candidate.strip()}”. This number was not matched to an approved fact. Verify it with a source before publishing.",
            "source": "Approved facts database"
        })

    lowered = text.lower()
    for word in data["avoid_words"]:
        if word.strip() and word.lower() in lowered:
            findings.append({
                "severity": "WARNING",
                "rule": "Avoided brand wording",
                "detail": f"“{word}” appears in the draft. Consider replacing it with approved brand language.",
                "source": "Brand voice settings"
            })

    if not findings:
        findings.append({
            "severity": "PASS",
            "rule": "Basic text checks",
            "detail": "No configured rule violations were detected. This does not prove every claim is true.",
            "source": "BrandGuard rule set"
        })
    return findings

def hex_to_rgb(value):
    value = value.strip().lstrip("#")
    return tuple(int(value[i:i+2], 16) for i in (0, 2, 4))

def scan_image(uploaded_file, colors):
    image = Image.open(uploaded_file).convert("RGB")
    image.thumbnail((500, 500))
    pixels = list(image.getdata())
    palette = [hex_to_rgb(color) for color in colors]
    matched = 0
    for pixel in pixels:
        nearest = min(sum((pixel[i] - color[i]) ** 2 for i in range(3)) for color in palette)
        if nearest < 55 ** 2:
            matched += 1
    ratio = matched / max(len(pixels), 1)
    return image, ratio

data = load_data()

st.markdown("""
<style>
:root { --navy:#173f86; --blue:#2454A6; --cream:#F5F1E7; --ink:#172033; --muted:#667085; --line:#E4E7EC; }
.stApp,[data-testid="stAppViewContainer"] { background:var(--cream); color:var(--ink); }
[data-testid="stHeader"] { background:rgba(245,241,231,.92); }
.block-container { max-width:1440px; padding-top:2rem; padding-bottom:3rem; }
h1,h2,h3,h4,p,li,label,.stMarkdown { color:var(--ink); }
h1 { font-size:2.2rem !important; font-weight:800 !important; letter-spacing:-.04em; }
h2,h3 { color:var(--navy) !important; font-weight:750 !important; }
[data-testid="stCaptionContainer"] { color:var(--muted) !important; }
section[data-testid="stSidebar"] { background:linear-gradient(180deg,#173f86,#12336f); }
section[data-testid="stSidebar"] * { color:#fff !important; }
section[data-testid="stSidebar"] hr { border-color:rgba(255,255,255,.2); }
div[data-testid="stTextInput"] input,div[data-testid="stTextArea"] textarea,
div[data-testid="stSelectbox"] [data-baseweb="select"] > div {
 background:#fff !important; color:var(--ink) !important;
 border:1px solid #D0D5DD !important; border-radius:10px !important;
}
div[data-testid="stTextInput"] input::placeholder,div[data-testid="stTextArea"] textarea::placeholder { color:#98A2B3 !important; }
div[data-testid="stSelectbox"] * { color:var(--ink) !important; }
div[data-testid="stButton"] button,div[data-testid="stFormSubmitButton"] button {
 background:var(--blue) !important; color:#fff !important; border:1px solid var(--blue) !important;
 border-radius:10px !important; min-height:2.7rem; font-weight:650;
}
div[data-testid="stButton"] button p,div[data-testid="stFormSubmitButton"] button p { color:#fff !important; }
div[data-testid="stButton"] button:hover,div[data-testid="stFormSubmitButton"] button:hover {
 background:#173f86 !important; border-color:#173f86 !important; color:#fff !important;
}
div[data-testid="stButton"] button:disabled { background:#D0D5DD !important; color:#667085 !important; border-color:#D0D5DD !important; }
div[data-testid="stMetric"] { background:#fff; border:1px solid var(--line); padding:1rem; border-radius:14px; }
div[data-testid="stMetric"] label,div[data-testid="stMetric"] [data-testid="stMetricValue"] { color:var(--ink) !important; }
div[data-testid="stExpander"],div[data-testid="stVerticalBlockBorderWrapper"] { background:#fff; border:1px solid var(--line); border-radius:12px; }
[data-testid="stFileUploaderDropzone"] { background:#fff !important; border:1px dashed #98A2B3 !important; border-radius:12px !important; }
hr { border-color:var(--line); }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.title("🛡️ BrandGuard")
    st.caption("Pre-flight governance for multichannel content")
    page = st.radio("Workspace", ["Content scanner", "Approval queue", "Brand settings", "How it works"])
    st.divider()
    st.caption("Brand: " + data["brand_name"])

if page == "Content scanner":
    st.title("Pre-flight content check")
    st.write("Check a draft against approved facts, brand voice and visual palette.")

    # Show the latest scan near the top so users get immediate feedback
    # without having to scroll past the input form.
    if "last_scan" in st.session_state:
        result = st.session_state["last_scan"]
        st.divider()
        st.subheader("Latest scan results")
        st.success("Scan complete — your results are ready.")
        st.caption(f"{result['title']} · {result['channel']}")

        pass_count = sum(item["severity"] == "PASS" for item in result["results"])
        warning_count = sum(item["severity"] == "WARNING" for item in result["results"])
        review_count = sum(item["severity"] == "REVIEW" for item in result["results"])
        m1, m2, m3 = st.columns(3)
        m1.metric("Passed", pass_count)
        m2.metric("Warnings", warning_count)
        m3.metric("Needs review", review_count)

        for item in result["results"]:
            icon = {"PASS": "🟢", "WARNING": "🟠", "REVIEW": "🔴"}.get(item["severity"], "🔵")
            with st.container(border=True):
                st.markdown(f"**{icon} {item['rule']}**")
                st.write(item["detail"])
                st.caption("Evidence / rule source: " + item["source"])

        if st.button("Send draft to manager approval", type="primary", key="send_latest_scan"):
            record = {
                "id": str(uuid.uuid4())[:8],
                "title": result["title"],
                "channel": result["channel"],
                "draft": result["draft"],
                "results": result["results"],
                "status": "Pending",
                "created": datetime.now().strftime("%Y-%m-%d %H:%M")
            }
            data["reviews"].append(record)
            save_data(data)
            st.success("Draft sent to the manager approval queue.")
        st.divider()

    left, right = st.columns([1.15, .85])
    with left:
        channel = st.selectbox("Publishing channel", ["Website", "LinkedIn", "Instagram", "Email", "Press release", "Other"])
        title = st.text_input("Content title", placeholder="e.g. Q3 product announcement")
        draft = st.text_area("Paste your draft", height=220, placeholder="Paste your content here...")
        run_scan = st.button("Run text checks", type="primary", use_container_width=True)
    with right:
        st.subheader("Visual linter")
        uploaded = st.file_uploader("Upload graphic (PNG/JPG)", type=["png", "jpg", "jpeg"])
        run_visual = st.button("Scan image", disabled=uploaded is None, use_container_width=True)

    if run_scan:
        if not draft.strip():
            st.error("Paste some content before running the scan.")
        else:
            results = scan_text(draft, data)
            st.session_state["last_scan"] = {
                "title": title.strip() or "Untitled draft",
                "channel": channel,
                "draft": draft,
                "results": results
            }
            st.toast("Scan complete! Results are displayed at the top of the page.", icon="✅")
            st.rerun()

    if run_visual and uploaded is not None:
        try:
            preview, ratio = scan_image(uploaded, data["colors"])
            st.session_state["visual_result"] = {"name": uploaded.name, "ratio": ratio}
            st.image(preview, caption=f"Preview: {uploaded.name}", width=350)
            if ratio >= 0.10:
                st.success(f"Palette check: {ratio:.1%} of sampled pixels are near your configured brand colors.")
            else:
                st.warning(f"Palette check: only {ratio:.1%} of sampled pixels are near your configured brand colors.")
            st.caption("This is a color-pixel heuristic only. It does not detect logo identity, spacing or full WCAG compliance.")
        except Exception as error:
            st.error(f"Could not read this image: {error}")

elif page == "Approval queue":
    st.title("Manager approval dashboard")
    reviews = data["reviews"]
    pending = sum(item["status"] == "Pending" for item in reviews)
    approved = sum(item["status"] == "Approved" for item in reviews)
    changes = sum(item["status"] == "Needs changes" for item in reviews)
    c1, c2, c3 = st.columns(3)
    c1.metric("Pending", pending)
    c2.metric("Approved", approved)
    c3.metric("Needs changes", changes)

    if not reviews:
        st.info("No drafts yet. Run a text scan and send a draft here.")
    for item in reversed(reviews):
        with st.expander(f"{item['title']} · {item['channel']} · {item['status']} · {item['id']}"):
            st.caption("Submitted: " + item["created"])
            st.write(item["draft"])
            for finding in item["results"]:
                st.write(f"{finding['severity']} — {finding['rule']}: {finding['detail']}")
            if item["status"] == "Pending":
                a, b = st.columns(2)
                if a.button("Approve", key="approve_" + item["id"], type="primary"):
                    item["status"] = "Approved"
                    save_data(data)
                    st.rerun()
                if b.button("Request changes", key="changes_" + item["id"]):
                    item["status"] = "Needs changes"
                    save_data(data)
                    st.rerun()

elif page == "Brand settings":
    st.title("Brand rules & approved facts")
    with st.form("brand_settings"):
        brand = st.text_input("Brand name", data["brand_name"])
        colors = st.text_input("Brand HEX colors, comma-separated", ", ".join(data["colors"]))
        tone = st.text_input("Preferred tone words", ", ".join(data["tone_words"]))
        avoid = st.text_input("Words / phrases to flag", ", ".join(data["avoid_words"]))
        facts = st.text_area(
            "Approved facts — one per line, format: claim | source",
            "\n".join(f"{fact['claim']} | {fact['source']}" for fact in data["facts"]),
            height=160
        )
        save_rules = st.form_submit_button("Save brand rules", type="primary")

    if save_rules:
        valid_colors = [color.strip().upper() for color in colors.split(",")
                        if re.fullmatch(r"#[0-9a-fA-F]{6}", color.strip())]
        parsed_facts = []
        for line in facts.splitlines():
            if line.strip():
                parts = line.split("|", 1)
                parsed_facts.append({
                    "claim": parts[0].strip(),
                    "source": parts[1].strip() if len(parts) > 1 else "User-provided approved fact"
                })
        if not valid_colors:
            st.error("Enter at least one valid HEX color, for example #2454A6.")
        else:
            data.update({
                "brand_name": brand.strip() or "My Brand",
                "colors": valid_colors,
                "tone_words": [word.strip() for word in tone.split(",") if word.strip()],
                "avoid_words": [word.strip() for word in avoid.split(",") if word.strip()],
                "facts": parsed_facts
            })
            save_data(data)
            st.success("Brand rules saved successfully.")

else:
    st.title("How BrandGuard works")
    st.write("Draft → checks → fix → manager approval → publish")
    st.markdown("**Fact-Fighter:** recognizes configured approved facts and flags unmatched numeric claims.")
    st.markdown("**Visual Linter:** estimates whether an uploaded image uses configured brand colors.")
    st.markdown("**Tone Thermometer:** flags configured words and phrases.")
    st.markdown("**Human-in-the-loop:** a manager explicitly approves or requests changes.")
    st.warning("This is a local MVP. Checks are rule-based heuristics, not AI fact verification. There is no publishing integration, authentication, full WCAG analysis or logo geometry detection.")
    st.subheader("Copy this test draft")
    st.code("We were founded in 2020 and now serve 12 countries. Our revolutionary platform guarantees 99% better results. We provide 24/7 customer support. Our platform has 5 million users.")
