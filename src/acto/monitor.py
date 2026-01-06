import altair as alt
import json
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from datetime import timedelta
from pathlib import Path
from streamlit_autorefresh import st_autorefresh
from tclogger import tcdatetime, get_now, get_now_ts, dt_to_str

STATUS_COLORS = {
    "create": "#333333",  # gray
    "run": "#ff9944",  # orange
    "done": "#44aa44",  # green
    "idle": "#336677",  # teal
    "error": "#aa4444",  # red
}
SEP_LABEL_COLOR = "#00ffff"  # cyan
SEP_RULE_COLOR = "#22bbbb"  # cyan
COLOR_DOMAIN = list(STATUS_COLORS.keys())
COLOR_RANGE = list(STATUS_COLORS.values())

TRACK_DAYS = 7
CUTOFF_DAYS = 1
REFRESH_INTERVAL = 15

STATUS_ICONS = {
    "create": "🟢",
    "done": "🟢",
    "idle": "🟢",
    "run": "🟠",
}
STATUS_TOOLTIP = {
    "create": "⚫",
    "run": "🟠",
    "done": "🟢",
    "idle": "⚫",
    "error": "🔴",
}

PAGE_TITLE = "Actions"
LOGS_DIR = "/home/asimov/repos/bili-scraper/logs"
ACTION_LOG_PATTERN = "action_*.log"

# Language settings
LANG = "zh"  # "zh" for Chinese, "en" for English
LANG_TOOLTIP_LABELS = {
    "zh": {
        "date": "日期",
        "start": "开始",
        "end": "结束",
        "duration": "时长",
        "status": "状态",
    },
    "en": {
        "date": "Date",
        "start": "Start",
        "end": "End",
        "duration": "Duration",
        "status": "Status",
    },
}
TOOLTIP_LABELS = LANG_TOOLTIP_LABELS[LANG]


def init_st_page():
    st.set_page_config(
        page_title=PAGE_TITLE,
        page_icon="📡",
        layout="wide",
        initial_sidebar_state="auto",
    )
    st.markdown(
        """
        <style>
            .stAppHeader {
            }
            .stMainBlockContainer{
                padding-top: 0px;
                padding-bottom: 0px;
            }
            h3 {
                font-size: 1.5rem !important;
                padding-top: 0.25rem !important;
                padding-bottom: 0.25rem !important;
            }
            div[data-testid="stElementContainer"]:has(> iframe[height="0"][data-testid="stIFrame"]) {
                display: none !important;
            }
            span[data-baseweb="tag"] {
                background-color: #393939 !important;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def init_st_bars():
    st.sidebar.title("Settings")
    log_dir = Path(st.sidebar.text_input("Logs Directory", LOGS_DIR))
    log_files = []
    if log_dir.exists() and log_dir.is_dir():
        log_files = sorted([str(p) for p in log_dir.glob(ACTION_LOG_PATTERN)])
    selected = st.sidebar.multiselect(
        "Select log files",
        options=log_files,
        default=log_files,
        format_func=lambda x: Path(x).name,
    )
    return selected


def inject_title(new_title: str):
    new_title_str = json.dumps(new_title)
    # ts_str is used to trigger page-reload in streamlit
    ts_str = f"<!-- {get_now_ts()} -->"
    set_title_js = (
        f"<script>window.parent.document.title = {new_title_str};\n{ts_str};</script>"
    )
    components.html(set_title_js, height=0)
    log_title_js = f"<script>console.log({new_title_str});\n{ts_str};</script>"
    components.html(log_title_js, height=0)


class ActionMonitor:
    def __init__(self, log_paths):
        self.log_paths = sorted([Path(p) for p in log_paths], reverse=False)
        self.events_by_file = {p.name: [] for p in self.log_paths}

    def get_cutoff_dt(self):
        dt = get_now() - timedelta(days=CUTOFF_DAYS)
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        return dt

    def get_track_dt(self):
        dt = get_now() - timedelta(days=TRACK_DAYS)
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        return dt

    def get_x_scale_domain(self):
        """Get x-axis scale domain based on CUTOFF_DAYS."""
        now = get_now()
        if now.tzinfo is not None:
            now = now.replace(tzinfo=None)
        cutoff_dt = self.get_cutoff_dt()
        return (cutoff_dt, now)

    def load_events(self):
        track_dt = self.get_track_dt()
        for path in self.log_paths:
            evs = []
            if path.exists():
                try:
                    # Read file content with retry for race condition
                    content = path.read_text(encoding="utf-8")
                    if not content.strip():
                        # Empty file
                        self.events_by_file[path.name] = []
                        continue
                    data = json.loads(content)
                except (json.JSONDecodeError, UnicodeDecodeError, OSError) as e:
                    # File being written or corrupted, keep previous data if exists
                    if path.name not in self.events_by_file:
                        self.events_by_file[path.name] = []
                    continue

                if not isinstance(data, list):
                    self.events_by_file[path.name] = []
                    continue

                for msg in data:
                    if (
                        not isinstance(msg, dict)
                        or "now" not in msg
                        or "action" not in msg
                    ):
                        continue
                    try:
                        dt = tcdatetime.fromisoformat(msg.get("now"))
                        # Ensure timezone-naive for consistency
                        if dt.tzinfo is not None:
                            dt = dt.replace(tzinfo=None)
                        if dt < track_dt:
                            continue
                        evs.append((dt, msg.get("action")))
                    except (ValueError, TypeError):
                        # Invalid datetime format, skip
                        continue
                evs.sort(key=lambda x: x[0])
            self.events_by_file[path.name] = evs

    def merge_segs(self, segs: list[dict]) -> list[dict]:
        """
        - If adjacent segs have the same status, merge them into one segment.
        - If timestamp of prev_end is same or after next_start,
        then adjust prev_end to be 1us before next_start.
        - Filter out invalid segments where start >= end.
        """
        if not segs:
            return []

        new_segs = []
        for seg in segs:
            if new_segs and new_segs[-1]["status"] == seg["status"]:
                new_segs[-1]["end"] = seg["end"]
            else:
                new_segs.append(seg.copy())  # Use copy to avoid modifying original

        # Adjust overlapping timestamps
        for i in range(len(new_segs) - 1):
            prev = new_segs[i]
            next = new_segs[i + 1]
            if prev["end"] >= next["start"]:
                prev["end"] = next["start"] - timedelta(microseconds=1)

        # Filter out invalid segments
        valid_segs = [seg for seg in new_segs if seg["start"] < seg["end"]]
        return valid_segs

    def get_segs_df(self, events):
        segs = []
        for i in range(len(events) - 1):
            dt, action = events[i]
            next_dt, next_action = events[i + 1]
            # Determine status based on current and next action
            if action == "create":
                # create -> any: waiting to run (create status)
                status = "create"
            elif action == "run":
                if next_action == "done":
                    # run -> done: completed successfully
                    status = "done"
                else:
                    # run -> run/create: error (abnormal)
                    status = "error"
            elif action == "done":
                # done -> any: idle period
                status = "idle"
            else:
                continue
            segs.append({"start": dt, "end": next_dt, "status": status})
        if events:
            dt, action = events[-1]
            if action == "create":
                status = "create"
            elif action == "run":
                status = "run"
            elif action == "done":
                status = "idle"
            else:
                status = None
            if status:
                now = get_now()
                # Ensure timezone-naive to match dt
                if now.tzinfo is not None:
                    now = now.replace(tzinfo=None)
                now = now.replace(microsecond=0)
                segs.append({"start": dt, "end": now, "status": status})
        segs = self.merge_segs(segs)
        if not segs:
            return pd.DataFrame(
                columns=["start", "end", "status", "duration", "status_display"]
            )
        df = pd.DataFrame(segs)
        df["start"] = pd.to_datetime(df["start"]).dt.tz_localize(None)
        df["end"] = pd.to_datetime(df["end"]).dt.tz_localize(None)
        df["duration"] = (df["end"] - df["start"]).apply(
            lambda x: dt_to_str(x, str_format="unit")
        )
        df["status_display"] = df["status"].apply(
            lambda x: f"{STATUS_TOOLTIP.get(x, '❓')} {x}"
        )
        return df

    def get_seps_df(self, df):
        """get 00:00 in between the min and max datetime in df"""
        min_dt = df["start"].min()
        max_dt = df["end"].max()
        seps = pd.date_range(
            start=min_dt.floor("D"),
            end=max_dt.ceil("D"),
            freq="D",
        )
        seps_df = pd.DataFrame({"sep": seps, "label": seps.strftime("%m-%d")})
        return seps_df

    def format_name(self, name: str):
        name = name.replace("action_", "").replace(".log", "")
        name = "_".join(seg.capitalize() for seg in name.split("_"))
        return name

    def validate_df(self, df: pd.DataFrame, name: str) -> bool:
        """Validate DataFrame has required structure and data."""
        if df.empty:
            return False
        required_cols = ["start", "end", "status"]
        if not all(col in df.columns for col in required_cols):
            st.subheader(f"❌ {self.format_name(name)}")
            st.error(f"Invalid data structure for {name}")
            return False
        if len(df) == 0:
            return False
        return True

    def create_chart(self, df: pd.DataFrame) -> alt.Chart:
        """Create Altair chart from DataFrame."""
        bars = (
            alt.Chart(df)
            .mark_bar(size=20)
            .encode(
                x=alt.X(
                    "start:T",
                    scale=alt.Scale(domain=self.get_x_scale_domain()),
                    axis=alt.Axis(format="%H:%M", labelAngle=0, title=None),
                ),
                x2="end:T",
                y=alt.value(20),
                color=alt.Color(
                    "status:N",
                    scale=alt.Scale(domain=COLOR_DOMAIN, range=COLOR_RANGE),
                    legend=None,
                ),
                tooltip=[
                    alt.Tooltip(
                        "start:T", title=TOOLTIP_LABELS["date"], format="%Y-%m-%d"
                    ),
                    alt.Tooltip(
                        "start:T",
                        title=TOOLTIP_LABELS["start"],
                        format="[%m/%d] %H:%M:%S",
                    ),
                    alt.Tooltip(
                        "end:T", title=TOOLTIP_LABELS["end"], format="[%m/%d] %H:%M:%S"
                    ),
                    alt.Tooltip("duration:N", title=TOOLTIP_LABELS["duration"]),
                    alt.Tooltip("status_display:N", title=TOOLTIP_LABELS["status"]),
                ],
            )
        )
        return bars.properties(height=80, width=800).interactive()

    def render_task(self, name: str, events: list) -> str:
        """Render a single task. Returns status icon or empty string."""
        header_str = self.format_name(name)
        try:
            df = self.get_segs_df(events)
            if not self.validate_df(df, name):
                st.subheader(header_str)
                st.info(f"No events in last {TRACK_DAYS} days for {name}.")
                return ""

            last_status = df["status"].iloc[-1]
            status_icon = STATUS_ICONS.get(last_status, "❓")
            st.subheader(f"{status_icon} {header_str}")

            chart = self.create_chart(df)
            spec = chart.to_dict()
            spec.setdefault("usermeta", {})["embedOptions"] = {"actions": False}
            st.vega_lite_chart(df, spec, use_container_width=True)

            return status_icon
        except Exception as e:
            st.subheader(f"❌ {header_str}")
            st.error(f"Rendering error for {name}: {str(e)}")
            return ""

    def render(self):
        st_autorefresh(interval=REFRESH_INTERVAL * 1000, key="refresh")
        self.load_events()
        status_icons: list[str] = []
        for name, events in self.events_by_file.items():
            icon = self.render_task(name, events)
            if icon:
                status_icons.append(icon)
                continue
        status_icons_str = "".join(status_icons)
        new_title = f"{status_icons_str} {PAGE_TITLE}"
        inject_title(new_title)


if __name__ == "__main__":
    init_st_page()
    selected = init_st_bars()
    monitor = ActionMonitor(selected)
    monitor.render()

    # streamlit run src/acto/monitor.py --server.address 0.0.0.0
