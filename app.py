import os, re, json, uuid, io, base64
from datetime import datetime
from pathlib import Path

import streamlit as st
from PIL import Image, ImageStat
from pypdf import PdfReader

st.set_page_config(page_title="BrandGuard", page_icon="🛡️", layout="wide")

APP_DIR = Path(__file__).parent
DATA_FILE = APP_DIR / "brandguard_data.json"

DEFAULT = {
    "brand_name": "Antyrix Demo Brand",
    "colors": ["#2454A6", "#F1E8D0", "#111111"],
    "tone_words": ["clear", "confident", "helpful"],
    "avoid_words": ["guaranteed", "best in the world", "revolutionary", "unbelievable"],
    "facts": [
        {"claim": "Founded in 2020", "source": "Approved company fact sheet"},
        {"claim": "Serving customers in 12 countries", "source": "Q3 company report"},
        {"claim": "24/7 customer support", "source": "Support policy v2"}
    ],
    "reviews": []
}

def load_data():
    if not DATA_FILE.exists():
        save_data(DEFAULT)
        return json.loads(json.dumps(DEFAULT))
    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        for key, value in DEFAULT.items():
            data.setdefault(key, json.loads(json.dumps(value)))
        return data
    except Exception:
        st.warning("Saved brand data could not be read. Loaded safe demo defaults.")
        return json.loads(json.dumps(DEFAULT))

def save_data(data):
    DATA_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def valid_hex(value):
    return bool(re.fullmatch(r"#[0-9A-Fa-f]{6}", str(value).strip()))

def hex_rgb(value):
    value = value.strip().lstrip("#")
    return tuple(int(value[i:i+2], 16) for i in (0,2,4))

def extract_pdf_text(uploaded):
    reader = PdfReader(io.BytesIO(uploaded.getvalue()))
    pages = []
    for i, page in enumerate(reader.pages):
        pages.append(f"[Page {i+1}]\n" + (page.extract_text() or ""))
    return "\n\n".join(pages).strip()

def parse_guideline_suggestions(text):
    """Conservative, editable suggestions; never silently auto-approve extracted rules."""
    color_matches = list(dict.fromkeys(re.findall(r"(?i)#(?:[0-9a-f]{6})\b", text)))
    avoid_candidates = []
    for line in text.splitlines():
        line_clean = line.strip(" •-*:\t")
        if re.search(r"(?i)(avoid|do not use|never use|prohibited|banned)", line_clean):
            quoted = re.findall(r"[\"'“”](.{2,60}?)[\"'“”]", line_clean)
            avoid_candidates.extend(quoted)
    return {
        "colors": [c.upper() for c in color_matches[:12]],
        "avoid_words": list(dict.fromkeys(avoid_candidates))[:30],
        "facts": []
    }

def get_api_key():
    try:
        key = st.secrets.get("OPENAI_API_KEY", "")
    except Exception:
        key = ""
    return key or os.getenv("OPENAI_API_KEY", "")

def ai_fact_check(draft, approved_facts):
    key = get_api_key()
    if not key:
        return None, "AI checking is not configured. Add OPENAI_API_KEY in Streamlit Secrets or environment variables."
    try:
        from openai import OpenAI
        client = OpenAI(api_key=key)
        facts_text = "\n".join(
            f"- {f.get('claim','')} (source: {f.get('source','unspecified')})"
            for f in approved_facts if f.get("claim")
        ) or "- No approved facts have been configured."
        prompt = f"""You are a careful brand-content claim reviewer.
Use ONLY the approved facts below as evidence. Do not treat draft claims as evidence.
For each factual claim in the draft, return:
claim, status (SUPPORTED, UNSUPPORTED, or REVIEW), explanation, supporting_source.
If no approved fact supports a claim, do not call it true; mark UNSUPPORTED or REVIEW.
Do not judge style or invent sources. Return valid JSON with key "claims" containing an array.
APPROVED FACTS:
{facts_text}

DRAFT:
{draft}"""
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            response_format={"type":"json_object"},
            messages=[
                {"role":"system","content":"Return only valid JSON. Be conservative and evidence-grounded."},
                {"role":"user","content":prompt}
            ]
        )
        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)
        claims = parsed.get("claims", [])
        return claims, None
    except Exception as e:
        return None, f"AI check failed: {str(e)[:240]}"

def local_text_scan(draft, data):
    findings = []
    lower = draft.lower()
    for fact in data.get("facts", []):
        claim = fact.get("claim", "").strip()
        if claim and claim.lower() in lower:
            findings.append(("PASS","Approved fact phrase found",
                f"Matched “{claim}”. Source: {fact.get('source','unspecified')}"))
    number_patterns = re.findall(
        r"\b\d+(?:[.,]\d+)?\s*(?:%|percent|million|billion|thousand|countries|users|customers|years?)?\b",
        draft, re.I
    )
    for number in number_patterns:
        if not any(number.lower() in f.get("claim","").lower() for f in data.get("facts",[])):
            findings.append(("REVIEW","Numerical claim needs verification",
                f"Found “{number.strip()}”. Verify it against an approved source."))
    for word in data.get("avoid_words", []):
        if word and word.lower() in lower:
            findings.append(("WARNING","Avoided wording",f"“{word}” appears in the draft."))
    if not findings:
        findings.append(("PASS","Basic rule checks","No configured rule violations detected. This does not prove every claim is true."))
    return findings

def image_palette_scan(image, brand_colors):
    im = image.convert("RGB")
    im.thumbnail((320,320))
    pixels = list(im.getdata())
    if not pixels:
        return 0.0
    rgb_colors = [hex_rgb(c) for c in brand_colors if valid_hex(c)]
    if not rgb_colors:
        return 0.0
    threshold = 55**2
    near = sum(
        min(sum((p[i]-c[i])**2 for i in range(3)) for c in rgb_colors) <= threshold
        for p in pixels
    )
    return near / len(pixels)

def image_to_data_url(upload):
    mime = "image/jpeg" if upload.type in ("image/jpeg","image/jpg") else "image/png"
    encoded = base64.b64encode(upload.getvalue()).decode("ascii")
    return f"data:{mime};base64,{encoded}"

def ai_visual_check(upload, brand_colors, brand_name):
    key = get_api_key()
    if not key:
        return None, "AI visual checks need OPENAI_API_KEY. Palette analysis still works without it."
    try:
        from openai import OpenAI
        client = OpenAI(api_key=key)
        data_url = image_to_data_url(upload)
        prompt = f"""Review this marketing creative for brand visual compliance for {brand_name}.
Configured brand colors: {', '.join(brand_colors)}.
Identify only visible, reasonably certain issues: likely color mismatch, text contrast/readability, and logo placement/clear-space issues if a logo is visible.
Do not claim exact WCAG compliance from an image alone. Return JSON with keys:
overall (PASS, WARNING, REVIEW), findings (array of objects with issue, severity, explanation, recommendation).
If uncertain, say REVIEW. Do not invent brand rules beyond the configured colors."""
        from openai import OpenAI
        client = OpenAI(api_key=key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            response_format={"type":"json_object"},
            messages=[
                {"role":"system","content":"Be cautious, describe only visible evidence, and return valid JSON."},
                {"role":"user","content":[
                    {"type":"text","text":prompt},
                    {"type":"image_url","image_url":{"url":data_url,"detail":"high"}}
                ]}
            ]
        )
        return json.loads(response.choices[0].message.content or "{}"), None
    except Exception as e:
        return None, f"Visual AI check failed: {str(e)[:240]}"

data = load_data()

# Theme
st.markdown("""
<style>
:root{--navy:#173f86;--blue:#2454A6;--cream:#F5F1E7;--ink:#172033;--muted:#667085;--line:#E4E7EC}
.stApp,[data-testid="stAppViewContainer"]{background:var(--cream);color:var(--ink)}
[data-testid="stHeader"]{background:rgba(245,241,231,.92)}
.block-container{max-width:1440px;padding-top:1.8rem;padding-bottom:3rem}
h1,h2,h3,p,label,.stMarkdown{color:var(--ink)}
h1{font-weight:800!important;letter-spacing:-.03em}
h2,h3{color:var(--navy)!important;font-weight:750!important}
section[data-testid="stSidebar"]{background:linear-gradient(180deg,#173f86,#12336f)}
section[data-testid="stSidebar"] *{color:#fff!important}
div[data-testid="stButton"]>button{background:var(--blue);color:#fff!important;border:1px solid var(--blue);border-radius:10px;min-height:2.6rem;font-weight:650}
div[data-testid="stButton"]>button:hover{background:#173f86;color:#fff!important}
div[data-testid="stButton"]>button:disabled{background:#D0D5DD;color:#667085!important}
div[data-testid="stTextInput"] input,div[data-testid="stTextArea"] textarea,div[data-testid="stFileUploader"] section{background:#fff!important;color:var(--ink)!important;border:1px solid #D0D5DD!important;border-radius:10px!important}
[data-testid="stFileUploaderDropzone"]{background:#fff!important;border:1px dashed #98A2B3!important}
[data-testid="stFileUploaderDropzone"] *{color:var(--ink)!important}
div[data-testid="stMetric"]{background:#fff;border:1px solid var(--line);padding:1rem;border-radius:12px}
hr{border-color:var(--line)}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.title("🛡️ BrandGuard")
    st.caption("Pre-flight governance for multichannel content")
    page = st.radio("Workspace", ["Content scanner","Approval queue","Brand settings","Guideline importer","How it works"])
    st.divider()
    st.caption("Brand: " + data.get("brand_name","BrandGuard"))
    st.caption("Round 3 prototype")

if page == "Content scanner":
    st.title("Pre-flight content check")
    st.write("Check a draft against approved facts, brand voice and visual palette.")
    if "scan_result" in st.session_state:
        result = st.session_state.scan_result
        st.success("Scan completed. Results are shown here.")
        c1,c2,c3 = st.columns(3)
        all_findings = result.get("findings",[])
        c1.metric("Findings",len(all_findings))
        c2.metric("Warnings",sum(x[0]=="WARNING" for x in all_findings))
        c3.metric("Needs review",sum(x[0]=="REVIEW" for x in all_findings))
        for sev, rule, detail in all_findings:
            with st.container(border=True):
                st.markdown(f"**{'🟢' if sev=='PASS' else '🟠' if sev=='WARNING' else '🔴'} {rule}**")
                st.write(detail)
        if result.get("ai_claims"):
            st.subheader("AI claim review")
            for claim in result["ai_claims"]:
                status = str(claim.get("status","REVIEW")).upper()
                st.markdown(f"**{status}: {claim.get('claim','Claim')}**")
                st.write(claim.get("explanation","No explanation returned."))
                if claim.get("supporting_source"):
                    st.caption("Evidence: "+str(claim["supporting_source"]))
        if st.button("Send draft to manager approval",type="primary",key="send_approval"):
            # Prevent duplicate submissions on repeated clicks / reruns.
            existing = next((r for r in data["reviews"] if r.get("scan_id")==result["scan_id"]),None)
            if existing:
                st.info("This scan is already in the approval queue.")
            else:
                data["reviews"].append({
                    "id":str(uuid.uuid4())[:8],"scan_id":result["scan_id"],
                    "title":result["title"],"channel":result["channel"],
                    "draft":result["draft"],"results":result["findings"],
                    "status":"Pending","created":datetime.now().strftime("%Y-%m-%d %H:%M")
                })
                save_data(data)
                st.success("Draft submitted to approval queue.")
        st.divider()

    left,right = st.columns([1.15,.85])
    with left:
        channel = st.selectbox("Publishing channel",["Website","LinkedIn","Instagram","Email","Press release","Other"])
        title = st.text_input("Content title",placeholder="e.g. Product launch announcement")
        draft = st.text_area("Paste your draft",height=220,placeholder="Paste content to scan...")
        run_scan = st.button("Run text checks",type="primary",use_container_width=True)
    with right:
        st.subheader("Visual linter")
        graphic = st.file_uploader("Upload graphic (PNG/JPG)",type=["png","jpg","jpeg"],key="visual_upload")
        run_visual = st.button("Scan image",disabled=graphic is None,use_container_width=True)
    if run_scan:
        if not draft.strip():
            st.error("Paste some text before running checks.")
        else:
            with st.spinner("Checking text and approved facts..."):
                findings = local_text_scan(draft,data)
                ai_claims, ai_error = ai_fact_check(draft,data.get("facts",[]))
                st.session_state.scan_result = {
                    "scan_id":str(uuid.uuid4()),"title":title.strip() or "Untitled draft",
                    "channel":channel,"draft":draft,"findings":findings,
                    "ai_claims":ai_claims,"ai_error":ai_error
                }
            st.rerun()
    if run_visual and graphic:
        try:
            image = Image.open(graphic).convert("RGB")
            st.image(image,caption=f"Preview: {graphic.name}",width=350)
            ratio = image_palette_scan(image,data.get("colors",[]))
            if ratio >= .10:
                st.success(f"Brand palette estimate: {ratio:.1%} of sampled pixels are near configured colors.")
            else:
                st.warning(f"Brand palette estimate: only {ratio:.1%} of sampled pixels are near configured colors.")
            visual_report, visual_error = ai_visual_check(graphic,data.get("colors",[]),data.get("brand_name","BrandGuard"))
            if visual_report:
                st.subheader("Advanced visual compliance")
                st.write("Overall:",visual_report.get("overall","REVIEW"))
                for item in visual_report.get("findings",[]):
                    st.markdown(f"**{item.get('severity','REVIEW')}: {item.get('issue','Visual finding')}**")
                    st.write(item.get("explanation",""))
                    if item.get("recommendation"):
                        st.caption("Suggested fix: "+item["recommendation"])
            elif visual_error:
                st.info(visual_error)
            st.caption("Palette score is a pixel heuristic. AI visual feedback is advisory and not a formal accessibility certification.")
        except Exception as e:
            st.error(f"Could not process this image: {e}")

    if st.session_state.get("scan_result",{}).get("ai_error"):
        st.info(st.session_state.scan_result["ai_error"])

elif page == "Guideline importer":
    st.title("Brand guideline importer")
    st.write("Upload a PDF, review extracted text and approve suggested rules before saving.")
    pdf = st.file_uploader("Upload brand guideline PDF",type=["pdf"],key="guideline_pdf")
    if pdf:
        try:
            extracted = extract_pdf_text(pdf)
            if not extracted:
                st.warning("No selectable text found. This PDF may be scanned; OCR is not included in this prototype.")
            st.text_area("Extracted guideline text",extracted,height=260,key="extracted_text")
            suggestions = parse_guideline_suggestions(extracted)
            st.subheader("Detected suggestions — review before saving")
            color_text = st.text_input("Detected HEX colors (editable)",", ".join(suggestions["colors"]),key="suggested_colors")
            avoid_text = st.text_input("Detected prohibited phrases (editable)",", ".join(suggestions["avoid_words"]),key="suggested_avoid")
            fact_lines = st.text_area("Approved facts to add (one per line: claim | source)",height=140,
                placeholder="Add facts only when you have verified them against the PDF.",key="suggested_facts")
            if st.button("Apply reviewed guideline rules",type="primary"):
                new_colors = [x.strip().upper() for x in color_text.split(",") if valid_hex(x.strip())]
                new_avoid = [x.strip() for x in avoid_text.split(",") if x.strip()]
                new_facts = []
                for line in fact_lines.splitlines():
                    if line.strip():
                        parts = line.split("|",1)
                        new_facts.append({"claim":parts[0].strip(),"source":parts[1].strip() if len(parts)>1 else pdf.name})
                if new_colors: data["colors"] = list(dict.fromkeys(new_colors))
                data["avoid_words"] = list(dict.fromkeys(data.get("avoid_words",[])+new_avoid))
                data["facts"] = data.get("facts",[])+new_facts
                save_data(data)
                st.success("Reviewed guideline rules saved to BrandGuard.")
        except Exception as e:
            st.error(f"Could not read this PDF: {e}")

elif page == "Approval queue":
    st.title("Manager approval dashboard")
    reviews = data.get("reviews",[])
    a,b,c = st.columns(3)
    a.metric("Pending",sum(r.get("status")=="Pending" for r in reviews))
    b.metric("Approved",sum(r.get("status")=="Approved" for r in reviews))
    c.metric("Needs changes",sum(r.get("status")=="Needs changes" for r in reviews))
    if not reviews: st.info("No drafts yet. Run a scan and submit one for approval.")
    for review in reversed(reviews):
        with st.expander(f"{review.get('title','Draft')} · {review.get('channel','')} · {review.get('status','Pending')} · {review.get('id','')}"):
            st.caption("Submitted: "+review.get("created",""))
            st.write(review.get("draft",""))
            for item in review.get("results",[]):
                if isinstance(item,(list,tuple)) and len(item)>=3:
                    st.write(f"{item[0]} — {item[1]}: {item[2]}")
                else:
                    st.write(item)
            if review.get("status")=="Pending":
                col1,col2 = st.columns(2)
                if col1.button("Approve",key="approve_"+review.get("id","")):
                    review["status"]="Approved"; save_data(data); st.rerun()
                if col2.button("Request changes",key="changes_"+review.get("id","")):
                    review["status"]="Needs changes"; save_data(data); st.rerun()

elif page == "Brand settings":
    st.title("Brand rules & approved facts")
    with st.form("brand_settings"):
        brand = st.text_input("Brand name",data.get("brand_name",""))
        colors = st.text_input("Brand HEX colors",", ".join(data.get("colors",[])))
        tone = st.text_input("Preferred tone words",", ".join(data.get("tone_words",[])))
        avoid = st.text_input("Words / phrases to flag",", ".join(data.get("avoid_words",[])))
        facts = st.text_area("Approved facts: one per line, claim | source",
            "\n".join(f"{f.get('claim','')} | {f.get('source','')}" for f in data.get("facts",[])),height=160)
        save_settings = st.form_submit_button("Save brand rules",type="primary")
    if save_settings:
        valid_colors = list(dict.fromkeys(x.strip().upper() for x in colors.split(",") if valid_hex(x.strip())))
        if not valid_colors:
            st.error("Enter at least one valid HEX color, such as #2454A6.")
        else:
            parsed_facts=[]
            for line in facts.splitlines():
                if line.strip():
                    parts=line.split("|",1)
                    parsed_facts.append({"claim":parts[0].strip(),"source":parts[1].strip() if len(parts)>1 else "User-provided"})
            data.update({"brand_name":brand.strip() or "BrandGuard","colors":valid_colors,
                "tone_words":[x.strip() for x in tone.split(",") if x.strip()],
                "avoid_words":[x.strip() for x in avoid.split(",") if x.strip()],"facts":parsed_facts})
            save_data(data); st.success("Brand rules saved.")

else:
    st.title("How BrandGuard works")
    st.write("Draft → checks → revise → manager approval → publish")
    st.markdown("**Fact-Fighter:** rule-based checks plus optional AI claim review against approved facts.")
    st.markdown("**Guideline importer:** extracts selectable text from PDF and suggests HEX colors and prohibited phrases for review.")
    st.markdown("**Visual Linter:** palette estimate plus optional AI advisory review for visible visual issues.")
    st.markdown("**Tone Thermometer:** flags configured words and phrases.")
    st.markdown("**Human approval:** managers approve or request changes.")
    st.warning("AI features require an OpenAI API key configured in Streamlit Secrets. PDF extraction does not OCR scanned PDFs. AI findings are advisory, not legal or compliance certification.")
