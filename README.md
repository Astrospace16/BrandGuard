# BrandGuard — fixed working MVP

## Run
Windows:
```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

macOS/Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Open http://localhost:8501.

## Test text scanner
Paste:
`We were founded in 2020 and now serve 12 countries. Our revolutionary platform guarantees 99% better results. We provide 24/7 customer support. Our platform has 5 million users.`

Expected:
- Approved facts recognized: founded in 2020, 12 countries, 24/7 customer support.
- Avoided wording: revolutionary, guarantees.
- Needs review: 99%, 5 million users.

After clicking Run text checks, scroll down to the **Text scan results** section below the form.

## Important
This is a rule-based prototype. It does not independently prove claims are true or use an external AI model. Image scanning is only a palette pixel heuristic.
