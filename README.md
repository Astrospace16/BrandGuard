# BrandGuard — Round 3 prototype

BrandGuard is a pre-flight brand governance prototype for checking content before publication.

## Features
- Rule-based text checks against manually approved brand facts
- Optional OpenAI claim review with supported / unsupported / review classifications and explanations
- PDF guideline text extraction, HEX color and prohibited-phrase suggestions, and manual review before applying
- Visual palette pixel heuristic
- Optional OpenAI image review for visible color, contrast/readability and logo-placement concerns
- Brand settings and manager approval queue
- Duplicate approval submission protection and basic empty/error handling

## Run locally
Python 3.10+ recommended.

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Enable AI checks
Create `.streamlit/secrets.toml` (do not commit it) with:

```toml
OPENAI_API_KEY = "your-api-key"
```

Or set the `OPENAI_API_KEY` environment variable. The app uses `gpt-4o-mini` through the OpenAI Python SDK for claim review and image feedback. Without a key, local rule checks and palette scoring still work, and the app explains that AI is not configured.

## Deploy on Streamlit Community Cloud
- Repository: your public GitHub repository
- Branch: `main`
- Main file: `app.py`
- Add `OPENAI_API_KEY` in App settings → Secrets if you want AI functionality.

## Data and limitations
- The app stores brand settings and approvals in `brandguard_data.json` beside `app.py`. This is suitable for a demo, not durable multi-user production storage. Streamlit Cloud filesystem changes may not persist across rebuilds/restarts.
- PDF extraction reads selectable PDF text; scanned PDFs need OCR and are reported as such.
- Guideline suggestions are heuristic and must be reviewed. Facts are not automatically trusted.
- AI outputs are advisory and can be wrong. They are not a substitute for legal, regulatory or accessibility certification.
- Visual palette score is a pixel heuristic. AI visual review is not a formal WCAG test.
- Do not commit API keys, private brand documents or customer data to a public repository.
