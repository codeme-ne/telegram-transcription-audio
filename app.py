"""Streamlit web UI for Telegram Voice Transcriber."""
from __future__ import annotations

import streamlit as st
from pathlib import Path
from datetime import date, timedelta

from telegram_voice_transcriber.async_helpers import run_async
from telegram_voice_transcriber.web_auth import WebAuthManager, AuthState
from telegram_voice_transcriber.tg_client import list_dialogs, TelegramCollector
from telegram_voice_transcriber.config import build_app_config
from telegram_voice_transcriber.download import MediaDownloader
from telegram_voice_transcriber.dry_run import DryRunReport
from telegram_voice_transcriber.export_md import MarkdownExporter
from telegram_voice_transcriber.filters import FilterConfig, MessageType
from telegram_voice_transcriber.pipeline import PipelineOptions, ProcessingPipeline
from telegram_voice_transcriber.state import ProcessingState
from telegram_voice_transcriber.transcribe import WhisperTranscriber
from telegram_voice_transcriber.writer import FileWriter

st.set_page_config(
    page_title="Telegram Voice Transcriber",
    page_icon="🎙️",
    layout="wide",
)

# Initialize session state
if "auth_manager" not in st.session_state:
    st.session_state.auth_manager = WebAuthManager()
if "dialogs" not in st.session_state:
    st.session_state.dialogs = []
if "processing" not in st.session_state:
    st.session_state.processing = False
if "result_markdown" not in st.session_state:
    st.session_state.result_markdown = None
if "since_date" not in st.session_state:
    st.session_state.since_date = date.today() - timedelta(days=7)
if "until_date" not in st.session_state:
    st.session_state.until_date = date.today()


def main():
    st.title("🎙️ Telegram Voice Transcriber")
    st.markdown("Transcribe Telegram voice messages locally using Whisper. No Premium required.")

    auth = st.session_state.auth_manager

    # Sidebar: Authentication
    with st.sidebar:
        st.header("🔐 Authentication")
        render_auth_section(auth)

    # Main content based on auth state
    if auth.state == AuthState.AUTHENTICATED:
        render_transcription_ui(auth)
    else:
        render_setup_instructions()


def render_auth_section(auth: WebAuthManager):
    """Render the authentication sidebar based on current state."""

    if auth.state == AuthState.NEEDS_CREDENTIALS:
        st.markdown("### Step 1: API Credentials")
        st.markdown("[Get credentials from my.telegram.org](https://my.telegram.org)")

        api_id = st.text_input("API ID", type="default")
        api_hash = st.text_input("API Hash", type="password")

        if st.button("Save Credentials", disabled=not (api_id and api_hash)):
            try:
                auth.set_credentials(api_id=int(api_id), api_hash=api_hash)
                run_async(auth.connect())
                if auth.state == AuthState.AUTHENTICATED:
                    st.success(f"Already logged in as {auth.user_info['name']}!")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    elif auth.state == AuthState.NEEDS_PHONE:
        st.markdown("### Step 2: Phone Number")
        phone = st.text_input("Phone (with country code)", placeholder="+1234567890")

        if st.button("Send Code", disabled=not phone):
            try:
                run_async(auth.send_code(phone))
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    elif auth.state == AuthState.NEEDS_CODE:
        st.markdown("### Step 3: Verification Code")
        st.info(f"Code sent to {auth.phone} **via Telegram app** (not SMS!)")
        code = st.text_input("Enter code")

        if st.button("Verify", disabled=not code):
            try:
                run_async(auth.verify_code(code))
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    elif auth.state == AuthState.NEEDS_2FA:
        st.markdown("### Step 3b: Two-Factor Authentication")
        password = st.text_input("2FA Password", type="password")

        if st.button("Submit", disabled=not password):
            try:
                run_async(auth.verify_2fa(password))
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    elif auth.state == AuthState.AUTHENTICATED:
        st.success(f"✅ Logged in as {auth.user_info['name']}")
        if st.button("Logout"):
            run_async(auth.disconnect())
            st.session_state.auth_manager = WebAuthManager()
            st.session_state.dialogs = []
            st.rerun()

    st.divider()
    render_session_controls(auth)


def render_setup_instructions():
    """Show instructions while not authenticated."""
    st.info("👈 Complete authentication in the sidebar to start transcribing.")

    with st.expander("📖 How to get Telegram API credentials (2 minutes)"):
        st.markdown("""
        1. Go to [my.telegram.org](https://my.telegram.org)
        2. Log in with your phone number
        3. Click "API development tools"
        4. Create a new application (any name)
        5. Copy the **API ID** and **API Hash**

        These are your personal credentials - the app runs locally and your data never leaves your computer.
        """)


def render_session_controls(auth: WebAuthManager):
    """Session export/import to avoid repeated logins."""
    st.markdown("🗝️ Session sichern/restore")
    col_export, col_import = st.columns(2)

    with col_export:
        if st.button("Session anzeigen", key="session_export_btn"):
            session_str = auth.export_session_string()
            if session_str:
                st.text_area(
                    "Session String (kopieren und offline sichern)",
                    value=session_str,
                    height=120,
                    key="session_export_area",
                )
                st.info("Nicht committen oder teilen. Sicher offline ablegen.")
            else:
                st.warning("Keine gespeicherte Session gefunden.")

    with col_import:
        session_input = st.text_input(
            "Session importieren",
            value="",
            type="password",
            help="Einen zuvor gesicherten Session-String einfügen, um Login zu überspringen.",
            key="session_import_input",
        )
        if st.button("Übernehmen", key="session_import_btn"):
            try:
                auth.import_session_string(session_input)
                run_async(auth.connect())
                if auth.state == AuthState.AUTHENTICATED:
                    st.success(f"Session importiert. Eingeloggt als {auth.user_info['name']}.")
                    st.rerun()
                else:
                    st.info("Session geladen. Falls sie abgelaufen ist, bitte Code erneut eingeben.")
            except Exception as e:
                st.error(f"Session-Import fehlgeschlagen: {e}")


def _apply_date_preset(preset: str) -> None:
    """Set since/until dates based on preset selection."""
    today = date.today()
    presets = {
        "7 Tage": 7,
        "2 Wochen": 14,
        "1 Monat": 30,
        "3 Monate": 90,
    }
    if preset in presets:
        st.session_state.since_date = today - timedelta(days=presets[preset])
        st.session_state.until_date = today


def render_transcription_ui(auth: WebAuthManager):
    """Main transcription interface when authenticated."""

    # Load dialogs if not loaded
    if not st.session_state.dialogs:
        with st.spinner("Loading your chats..."):
            st.session_state.dialogs = run_async(list_dialogs(auth.client))

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("📋 Configuration")

        # Chat selection
        dialog_options = {d["name"]: d["id"] for d in st.session_state.dialogs}
        selected_chat = st.selectbox(
            "Select chat",
            options=list(dialog_options.keys()),
            help="Choose which chat to transcribe"
        )

        # Date range selection
        st.markdown("**Zeitraum**")
        preset = st.radio(
            "Schnellauswahl",
            options=["7 Tage", "2 Wochen", "1 Monat", "3 Monate", "Benutzerdefiniert"],
            horizontal=True,
            label_visibility="collapsed",
        )
        if preset != "Benutzerdefiniert":
            _apply_date_preset(preset)

        if preset == "Benutzerdefiniert":
            col_from, col_to = st.columns(2)
            with col_from:
                since_date = st.date_input(
                    "Von",
                    value=st.session_state.since_date,
                    key="since_picker",
                )
            with col_to:
                until_date = st.date_input(
                    "Bis",
                    value=st.session_state.until_date,
                    key="until_picker",
                )

            # Update session state if manually changed
            st.session_state.since_date = since_date
            st.session_state.until_date = until_date
        else:
            st.caption(f"Von: {st.session_state.since_date} · Bis (inkl.): {st.session_state.until_date}")

        # Message types
        message_types = st.multiselect(
            "Message types",
            options=["voice", "audio", "video_note", "text"],
            default=["voice", "text"],
        )

    with col2:
        st.subheader("⚙️ Options")

        include_self = st.checkbox("Include my messages", value=False)
        language = st.selectbox("Language", ["de", "en", "fr", "es", "it"], index=0)
        model_size = st.selectbox(
            "Whisper model",
            ["tiny", "base", "small", "medium"],
            index=2,
            help="Larger = more accurate but slower"
        )
        dry_run = st.checkbox("Dry run (preview only)", value=True)

    st.divider()

    # Process button
    if st.button("🚀 Start Transcription", type="primary", use_container_width=True):
        if not selected_chat:
            st.error("Please select a chat")
            return

        process_transcription(
            auth=auth,
            chat_id=dialog_options[selected_chat],
            chat_name=selected_chat,
            since_date=st.session_state.since_date,
            until_date=st.session_state.until_date,
            message_types=message_types,
            include_self=include_self,
            language=language,
            model_size=model_size,
            dry_run=dry_run,
        )

    # Show results if available
    if st.session_state.result_markdown:
        st.divider()
        st.subheader("📄 Result")
        st.download_button(
            "⬇️ Download Markdown",
            data=st.session_state.result_markdown,
            file_name=f"transcript-{st.session_state.since_date}-{st.session_state.until_date}.md",
            mime="text/markdown",
        )
        with st.expander("Preview"):
            st.markdown(st.session_state.result_markdown[:5000] + "..." if len(st.session_state.result_markdown) > 5000 else st.session_state.result_markdown)


def process_transcription(
    auth: WebAuthManager,
    chat_id: int,
    chat_name: str,
    since_date: date,
    until_date: date,
    message_types: list[str],
    include_self: bool,
    language: str,
    model_size: str,
    dry_run: bool,
):
    """Run the transcription pipeline with progress updates."""
    year = since_date.year  # For path compatibility
    until_exclusive = until_date + timedelta(days=1)

    base_dir = Path(".data/web")
    base_dir.mkdir(parents=True, exist_ok=True)

    config = build_app_config(
        api_id=auth.api_id,
        api_hash=auth.api_hash,
        session_file=auth.session_path,
        chat_identifier=str(chat_id),
        year=year,
        include_self=include_self,
        include_types=message_types,
        include_message_ids=True,
        timezone_name="Europe/Vienna",
        dry_run=dry_run,
        language=language,
        model_size=model_size,
        base_dir=base_dir,
        since_date=since_date.strftime("%Y-%m-%d"),
        until_date=until_exclusive.strftime("%Y-%m-%d"),
    )

    with st.status("Processing...", expanded=True) as status:
        # Collect messages
        st.write("📥 Collecting messages from Telegram...")
        collector = TelegramCollector(auth.client)
        collector_filter = FilterConfig(
            allowed_sender_ids=None,
            allowed_types=set(MessageType(t) for t in message_types),
            year=None,
            include_self=True,
        )

        collection = run_async(collector.collect(
            chat_identifier=chat_id,
            filter_config=collector_filter,
            since=config.date_range.since,
            until=config.date_range.until,
        ))

        st.write(f"Found {len(collection.messages)} messages")

        if not collection.messages:
            status.update(label="No messages found", state="complete")
            return

        # Setup pipeline
        state = ProcessingState(config.paths.state_path)
        downloader = MediaDownloader(client=auth.client, base_dir=config.paths.cache_dir)
        exporter = MarkdownExporter(
            chat_title=chat_name,
            year=year,
            include_message_ids=True,
            timezone_name=config.timezone,
        )
        dry_run_report = DryRunReport(chat_title=chat_name, year=year)

        # Determine sender filtering
        sender_ids = {m.sender_id for m in collection.messages if m.sender_id}
        if collection.self_user_id and not include_self:
            sender_ids.discard(collection.self_user_id)

        # Load Whisper model if needed
        if not dry_run:
            st.write(f"🤖 Loading Whisper model ({model_size})...")
            from faster_whisper import WhisperModel
            models_dir = config.paths.cache_dir.parent / "models"
            models_dir.mkdir(parents=True, exist_ok=True)
            model = WhisperModel(model_size, device="auto", compute_type="int8", download_root=str(models_dir))
            transcriber = WhisperTranscriber(model=model, language=language)
        else:
            transcriber = _DummyTranscriber()

        pipeline = ProcessingPipeline(
            options=PipelineOptions(dry_run=dry_run, output_path=config.paths.output_path),
            filter_config=FilterConfig(
                allowed_sender_ids=sender_ids or None,
                allowed_types=set(MessageType(t) for t in message_types),
                year=None,
                include_self=include_self,
            ),
            exporter=exporter,
            dry_run_report=dry_run_report,
            downloader=downloader,
            transcriber=transcriber,
            writer=FileWriter(),
            state=state,
            self_user_id=collection.self_user_id,
        )

        # Run pipeline
        st.write("⚙️ Processing messages...")
        result = run_async(pipeline.run(collection.messages))

        if dry_run:
            status.update(label="Dry run complete!", state="complete")
            st.write(f"Would process {result.total_messages} messages")
            for msg_type, count in result.type_counts.items():
                st.write(f"  - {msg_type.value}: {count}")
        else:
            status.update(label="Transcription complete!", state="complete")
            st.write(f"Processed {result.processed_messages} messages")

            # Load result for download
            if result.output_path and result.output_path.exists():
                st.session_state.result_markdown = result.output_path.read_text()


class _DummyTranscriber:
    def transcribe(self, audio_path):
        return "[Dry run - no transcription]"


if __name__ == "__main__":
    main()
