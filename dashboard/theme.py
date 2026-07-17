"""Theme tokens, custom CSS and small HTML helpers shared by all tabs.

Palette (enterprise banking, dark):
  bg deep navy #0B1220 / panel #121B2E / card #17233A
  AI accents cyan #38BDF8 / blue #60A5FA
  risk: emerald #34D399 (low/approved), amber #FBBF24 (medium/warning),
        orange #FB923C (high), red #F87171 (critical/rejected)
"""
from __future__ import annotations

RISK_COLORS = {"Low": "#34D399", "Medium": "#FBBF24",
               "High": "#FB923C", "Critical": "#F87171"}
STATUS_COLORS = {
    "Drafted": "#60A5FA", "Pending Review": "#FBBF24", "Approved": "#34D399",
    "Approved with edits": "#34D399", "Overridden": "#38BDF8",
    "Rejected": "#F87171", "Escalated": "#C084FC",
    "Dignified Goodbye": "#5EEAD4", "Logged": "#94A3B8",
}
LANG_NAMES = {"en": "English", "ar": "Arabic", "hi": "Hindi (romanized)",
              "tl": "Tagalog"}

CSS = """
body, .gradio-container { background: #0B1220 !important; }
.gradio-container { max-width: 1440px !important; margin: 0 auto; }
#wafa-header { background: linear-gradient(90deg, #101A30 0%, #0E1830 60%, #12213E 100%);
  border: 1px solid #1E2A44; border-radius: 12px; padding: 18px 22px; margin-bottom: 6px; }
#wafa-header h1 { color: #E2E8F0; font-size: 26px; margin: 0; letter-spacing: 0.5px; }
#wafa-header .sub { color: #7DA2CE; font-size: 14px; margin-top: 2px; }
.badge { display: inline-block; padding: 3px 10px; border-radius: 999px;
  font-size: 11.5px; font-weight: 600; letter-spacing: 0.4px; margin-right: 6px;
  border: 1px solid; white-space: nowrap; }
.wcard { background: #121B2E; border: 1px solid #1E2A44; border-radius: 10px;
  padding: 14px 16px; margin: 4px 0; color: #CBD5E1; }
.wcard h3, .wcard h4 { color: #E2E8F0; margin: 0 0 8px 0; }
.wcard .k { color: #7DA2CE; font-size: 12px; }
.wcard .v { color: #E2E8F0; font-size: 15px; font-weight: 600; }
.metric-row { display: flex; gap: 10px; flex-wrap: wrap; }
.metric { flex: 1; min-width: 140px; background: #17233A; border: 1px solid #24314E;
  border-radius: 10px; padding: 12px 14px; }
.metric .label { color: #7DA2CE; font-size: 11.5px; text-transform: uppercase; letter-spacing: 0.6px; }
.metric .value { color: #E8EEF7; font-size: 22px; font-weight: 700; margin-top: 2px; }
.metric .note { color: #64748B; font-size: 11.5px; margin-top: 2px; }
.gaugewrap { background: #0E1626; border-radius: 999px; height: 14px; overflow: hidden;
  border: 1px solid #1E2A44; margin: 6px 0; }
.gaugefill { height: 100%; border-radius: 999px; }
.rtl { direction: rtl; text-align: right; font-size: 17px; line-height: 1.9; }
.msgbox { background: #0E1626; border: 1px solid #24314E; border-left: 3px solid #38BDF8;
  border-radius: 0 8px 8px 0; padding: 12px 14px; color: #DBEAFE; }
.warn { background: #2A2010; border: 1px solid #7C5A16; border-left: 4px solid #FBBF24;
  border-radius: 0 8px 8px 0; padding: 10px 14px; color: #FDE68A; }
.crit { background: #2A1214; border: 1px solid #7F2B2B; border-left: 4px solid #F87171;
  border-radius: 0 8px 8px 0; padding: 10px 14px; color: #FECACA; }
.ok { background: #0E241C; border: 1px solid #14532D; border-left: 4px solid #34D399;
  border-radius: 0 8px 8px 0; padding: 10px 14px; color: #A7F3D0; }
.gov { background: #131B30; border: 1px solid #26314E; border-left: 4px solid #7DA2CE;
  border-radius: 0 8px 8px 0; padding: 10px 14px; color: #B9C8DD; margin: 5px 0; }
.timeline { border-left: 2px solid #24314E; margin-left: 8px; padding-left: 16px; }
.tstep { margin-bottom: 10px; position: relative; }
.tstep::before { content: ""; position: absolute; left: -21.5px; top: 4px; width: 9px;
  height: 9px; border-radius: 50%; background: #38BDF8; }
.tstep.human::before { background: #34D399; }
.tstep .t { color: #64748B; font-size: 11px; }
.tstep .s { color: #DCE7F5; font-size: 13.5px; }
.rulebox { background: #0E1626; border: 1px solid #24314E; border-radius: 8px;
  padding: 10px 14px; font-family: ui-monospace, Consolas, monospace;
  font-size: 12.5px; color: #A5C8EC; white-space: pre-wrap; }
.footer-disclaimer { color: #64748B; font-size: 11.5px; text-align: center; margin-top: 10px; }
"""


def badge(text: str, color: str) -> str:
    return (f"<span class='badge' style='color:{color}; border-color:{color}55; "
            f"background:{color}18'>{text}</span>")


def risk_badge(band: str) -> str:
    return badge(f"{band.upper()} RISK", RISK_COLORS.get(band, "#94A3B8"))


def status_badge(status: str) -> str:
    return badge(status.upper(), STATUS_COLORS.get(status, "#94A3B8"))


def conf_badge(label: str, conf: float) -> str:
    color = "#34D399" if conf >= 0.75 else "#FBBF24" if conf >= 0.5 else "#F87171"
    return badge(f"{label} {conf:.0%}", color)


def gauge(pct: float, band: str) -> str:
    color = RISK_COLORS.get(band, "#94A3B8")
    return (f"<div class='gaugewrap'><div class='gaugefill' "
            f"style='width:{max(2, min(100, pct)):.0f}%; background:{color}'>"
            f"</div></div>")


def metric(label: str, value: str, note: str = "") -> str:
    n = f"<div class='note'>{note}</div>" if note else ""
    return (f"<div class='metric'><div class='label'>{label}</div>"
            f"<div class='value'>{value}</div>{n}</div>")


def metric_row(*metrics: str) -> str:
    return "<div class='metric-row'>" + "".join(metrics) + "</div>"


def card(title: str, body_html: str) -> str:
    return f"<div class='wcard'><h4>{title}</h4>{body_html}</div>"


def aed(x: float) -> str:
    return f"AED {x:,.0f}"


def msg_html(text: str, lang: str) -> str:
    rtl = " rtl" if lang == "ar" else ""
    safe = (text or "").replace("<", "&lt;").replace(">", "&gt;")
    return f"<div class='msgbox{rtl}'>{safe}</div>"
