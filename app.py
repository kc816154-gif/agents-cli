import base64
import os
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

import requests
import streamlit as st
from dotenv import load_dotenv

# ----------------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------------
load_dotenv()

DB_PATH = Path(__file__).parent / "studio.db"
OPENAI_MODEL = "gpt-4o-mini"
CLAUDE_MODEL = "claude-3-5-haiku-latest"
HTTP_TIMEOUT = 90
MAX_HISTORY = 10  # messages sent to the model as context

SYSTEM_PROMPT = (
    "You are KRISHN AI STUDIO, a helpful multilingual creative and coding "
    "assistant. Answer clearly, give practical steps, and use code blocks "
    "when showing code."
)

st.set_page_config(page_title="KRISHN AI STUDIO", page_icon="✨", layout="wide")

st.markdown("""
<style>
.stApp{background:radial-gradient(circle at 80% 0%,#172554 0,#090d18 40%);color:#f8fafc}
section[data-testid="stSidebar"]{background:#101827}
.hero{padding:28px;border:1px solid #334155;border-radius:20px;
      background:linear-gradient(120deg,#172554,#111827,#312e81)}
.hero h1{font-size:2.3rem;color:white;margin:0}
.hero p{color:#cbd5e1}
.tile{padding:16px;border:1px solid #334155;border-radius:16px;
      background:#111827;min-height:100px}
</style>
""", unsafe_allow_html=True)


# ----------------------------------------------------------------------------
# HELPERS
# ----------------------------------------------------------------------------
def get_secret(name: str):
    """Read from env first, then Streamlit secrets (Cloud friendly)."""
    value = os.getenv(name)
    if value:
        return value
    try:
        value = st.secrets.get(name)
        return str(value) if value else None
    except Exception:
        return None


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS drafts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            title TEXT NOT NULL,
            caption TEXT,
            publish_date TEXT,
            status TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    return conn


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def openai_chat(prompt: str, history: list[dict]) -> str:
    key = get_secret("OPENAI_API_KEY")
    if not key:
        return "OPENAI_API_KEY missing. Add it in Streamlit Secrets or studio/.env."

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += [{"role": m["role"], "content": m["content"]} for m in history[-MAX_HISTORY:]]
    messages.append({"role": "user", "content": prompt})

    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": OPENAI_MODEL, "messages": messages},
        timeout=HTTP_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def claude_chat(prompt: str) -> str:
    key = get_secret("ANTHROPIC_API_KEY")
    if not key:
        return "ANTHROPIC_API_KEY missing. Add it in Streamlit Secrets or studio/.env."

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": CLAUDE_MODEL,
            "max_tokens": 1600,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=HTTP_TIMEOUT,
    )
    resp.raise_for_status()
    return "".join(block.get("text", "") for block in resp.json().get("content", []))


def generate_image(prompt: str) -> bytes:
    key = get_secret("OPENAI_API_KEY")
    if not key:
        raise ValueError("OPENAI_API_KEY missing. Add it in Settings.")

    resp = requests.post(
        "https://api.openai.com/v1/images/generations",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": "gpt-image-1", "prompt": prompt, "size": "1024x1024"},
        timeout=180,
    )
    resp.raise_for_status()
    item = resp.json()["data"][0]

    if item.get("b64_json"):
        return base64.b64decode(item["b64_json"])
    if item.get("url"):
        return requests.get(item["url"], timeout=60).content
    raise ValueError("No image data returned by the API.")


# ----------------------------------------------------------------------------
# SIDEBAR
# ----------------------------------------------------------------------------
st.sidebar.title("✨ KRISHN AI STUDIO")
st.sidebar.caption("ONE AI. ALL SKILLS. ONE STUDIO.")

page = st.sidebar.radio(
    "WORKSPACE",
    [
        "Dashboard", "AI Chat", "Claude AI", "PhotoCraft", "FilmCraft",
        "GitHub Agent", "SocialCraft", "WebsiteCraft", "Craft Tools", "Settings",
    ],
)

st.sidebar.divider()
st.sidebar.caption(
    f"OpenAI {'✅' if get_secret('OPENAI_API_KEY') else '❌'} · "
    f"Claude {'✅' if get_secret('ANTHROPIC_API_KEY') else '❌'} · "
    f"GitHub {'✅' if get_secret('GITHUB_TOKEN') else '❌'}"
)


# ----------------------------------------------------------------------------
# PAGES
# ----------------------------------------------------------------------------
if page == "Dashboard":
    st.markdown(
        '<div class="hero"><h1>KRISHN AI STUDIO</h1>'
        "<p>Your all-in-one creative and AI workspace.</p></div>",
        unsafe_allow_html=True,
    )
    st.write("")

    cols = st.columns(3)
    tiles = [
        ("🤖 AI Assistant", "ChatGPT-powered chat"),
        ("🎨 PhotoCraft", "Text-to-image generation"),
        ("🎬 FilmCraft", "AI video workflow"),
    ]
    for col, (title, desc) in zip(cols, tiles):
        with col:
            st.markdown(
                f'<div class="tile"><b>{title}</b><p>{desc}</p></div>',
                unsafe_allow_html=True,
            )

    st.subheader("Modules")
    st.write(
        "ChatGPT • Claude • GitHub • Image • Video • Website • "
        "Social Media • Documents • Automation"
    )
    st.info("Open Settings to check API configuration. Paid API usage may apply.")

elif page == "AI Chat":
    st.title("🤖 AI Chat")

    if "history" not in st.session_state:
        st.session_state.history = []

    col1, col2 = st.columns([6, 1])
    with col2:
        if st.button("Clear", use_container_width=True):
            st.session_state.history = []
            st.rerun()

    for msg in st.session_state.history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    prompt = st.chat_input("Ask KRISHN AI...")
    if prompt:
        with st.chat_message("user"):
            st.write(prompt)
        with st.chat_message("assistant"):
            try:
                with st.spinner("Thinking..."):
                    answer = openai_chat(prompt, st.session_state.history)
                st.markdown(answer)
                st.session_state.history.append({"role": "user", "content": prompt})
                st.session_state.history.append({"role": "assistant", "content": answer})
            except Exception as exc:
                st.error(f"OpenAI error: {exc}")

elif page == "Claude AI":
    st.title("🧠 Claude AI")
    prompt = st.text_area("Your prompt", height=180)
    if st.button("Ask Claude", type="primary", disabled=not prompt.strip()):
        try:
            with st.spinner("Thinking..."):
                st.markdown(claude_chat(prompt))
        except Exception as exc:
            st.error(f"Claude error: {exc}")

elif page == "PhotoCraft":
    st.title("🎨 PhotoCraft – Image Generator")
    prompt = st.text_area(
        "Describe your image",
        height=140,
        placeholder="Cinematic product photo, detailed lighting...",
    )
    st.caption("Uses the OpenAI image API; generation may incur charges.")

    if st.button("Generate image", type="primary", disabled=not prompt.strip()):
        try:
            with st.spinner("Generating..."):
                data = generate_image(prompt)
            st.image(data, caption=prompt[:120], use_container_width=True)
            st.download_button("Download PNG", data, "krishn-image.png", "image/png")
        except Exception as exc:
            st.error(f"Image error: {exc}")

elif page == "FilmCraft":
    st.title("🎬 FilmCraft – Video Studio")
    prompt = st.text_area("Describe your video", height=140)
    ratio = st.selectbox("Format", ["9:16 Reels", "16:9 YouTube", "1:1 Square"])
    st.info(
        "Video rendering needs a provider/model, API token and credits. "
        "This MVP prepares the workflow; it does not fake a finished video."
    )
    if st.button("Prepare video job"):
        if not prompt.strip():
            st.warning("Enter a video prompt.")
        elif not get_secret("REPLICATE_API_TOKEN"):
            st.warning(
                "Add REPLICATE_API_TOKEN in Streamlit Secrets before "
                "connecting a Replicate model."
            )
        else:
            st.success(
                "Video prompt prepared. Provider model/version integration is "
                f"the next build step. Format: {ratio}"
            )

elif page == "GitHub Agent":
    st.title("🐙 GitHub Agent")
    repo = st.text_input("Repository", "kc816154-gif/agents-cli")

    if st.button("Inspect repository"):
        headers = {"Accept": "application/vnd.github+json"}
        token = get_secret("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            resp = requests.get(
                f"https://api.github.com/repos/{repo}", headers=headers, timeout=30
            )
            resp.raise_for_status()
            data = resp.json()
            st.success(f"{data['full_name']} • Branch: {data['default_branch']}")
            st.write(data.get("description") or "No description")
            c1, c2, c3 = st.columns(3)
            c1.metric("Stars", data.get("stargazers_count", 0))
            c2.metric("Forks", data.get("forks_count", 0))
            c3.metric("Open issues", data.get("open_issues_count", 0))
            st.link_button("Open GitHub", data["html_url"])
        except Exception as exc:
            st.error(f"GitHub error: {exc}")

    st.caption(
        "This version reads repository metadata only. Write operations will "
        "require scoped authorization and explicit confirmation."
    )

elif page == "SocialCraft":
    st.title("📱 SocialCraft – Content Planner")
    st.caption("Save drafts and planned dates. Automatic publishing is not enabled yet.")

    with st.form("draft_form", clear_on_submit=True):
        platform = st.selectbox("Platform", ["Instagram", "YouTube", "Facebook"])
        title = st.text_input("Title")
        caption = st.text_area("Caption and hashtags")
        day = st.date_input("Planned date", value=date.today())
        submitted = st.form_submit_button("Save draft")

    if submitted:
        if not title.strip():
            st.warning("Title is required.")
        else:
            conn = get_conn()
            try:
                conn.execute(
                    "INSERT INTO drafts(platform,title,caption,publish_date,status,created_at)"
                    " VALUES(?,?,?,?,?,?)",
                    (platform, title.strip(), caption, str(day), "Draft", utc_now_iso()),
                )
                conn.commit()
                st.success("Draft saved.")
            finally:
                conn.close()

    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT id, platform, title, caption, publish_date, status "
            "FROM drafts ORDER BY id DESC"
        ).fetchall()
    finally:
        conn.close()

    st.subheader("Saved drafts")
    if not rows:
        st.info("No drafts yet.")
    for row in rows:
        with st.expander(f"{row['publish_date']} • {row['platform']} • {row['title']}"):
            st.write(row["caption"] or "—")
            st.caption(row["status"])
            if st.button("Delete", key=f"del_{row['id']}"):
                conn = get_conn()
                try:
                    conn.execute("DELETE FROM drafts WHERE id=?", (row["id"],))
                    conn.commit()
                finally:
                    conn.close()
                st.rerun()

elif page == "WebsiteCraft":
    st.title("🌐 WebsiteCraft")
    idea = st.text_area("Describe your website")
    if st.button("Create website prompt", disabled=not idea.strip()):
        st.code(
            "Build a mobile-first, responsive website for: "
            f"{idea}\n\n"
            "Requirements:\n"
            "- Accessible semantic HTML\n"
            "- SEO metadata (title, description, Open Graph)\n"
            "- Clean, modern CSS (no heavy frameworks unless requested)\n"
            "- Plain JavaScript with no build step\n"
            "- Include setup/run instructions",
            language="text",
        )
    st.info("Use AI Chat to generate the actual HTML/CSS/JS project. ZIP export is planned.")

elif page == "Craft Tools":
    st.title("🧰 Craft Tools")
    items = {
        "VectorCraft": "Logo and SVG workflows",
        "LightCraft": "Image enhancement",
        "EffectCraft": "Video effects",
        "DesignCraft": "Posters and thumbnails",
        "SoundCraft": "Voice and audio workflows",
        "PdfCraft": "PDF tools",
        "WordCraft": "Documents",
        "DeckCraft": "Presentations",
        "GridCraft": "Spreadsheets",
        "CADCraft": "CAD design workflows",
    }
    cols = st.columns(2)
    for i, (name, desc) in enumerate(items.items()):
        with cols[i % 2]:
            st.markdown(
                f'<div class="tile"><b>{name}</b><p>{desc}</p></div>',
                unsafe_allow_html=True,
            )
            st.write("")

elif page == "Settings":
    st.title("⚙️ API Settings")
    st.warning("Never put real API keys in source code or public GitHub files.")

    for key, label in [
        ("OPENAI_API_KEY", "OpenAI"),
        ("ANTHROPIC_API_KEY", "Claude"),
        ("GITHUB_TOKEN", "GitHub"),
        ("REPLICATE_API_TOKEN", "Video provider"),
    ]:
        configured = bool(get_secret(key))
        st.write(f"{label}: {'✅ Configured' if configured else '❌ Not configured'}")

    st.markdown("**Streamlit Cloud:** App → Settings → Secrets")
    st.code(
        'OPENAI_API_KEY = "your-key"\n'
        'ANTHROPIC_API_KEY = "your-key"\n'
        'GITHUB_TOKEN = "your-token"\n'
        'REPLICATE_API_TOKEN = "your-token"',
        language="toml",
    )
    st.markdown("**Local:** create a `.env` file next to `app.py` with the same keys.")