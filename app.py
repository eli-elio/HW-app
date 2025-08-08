import os
import pandas as pd
import plotly.graph_objects as go
from dash import Dash, dcc, html, Input, Output

# ========= Paths =========
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HWI_CSV = os.path.join(BASE_DIR, "data", "LV_average_HWI.csv")
HW_CSV  = os.path.join(BASE_DIR, "data", "LV_average_HWdays.csv")

# ========= Load HWI =========
hwi = pd.read_csv(HWI_CSV, parse_dates=["time"])
hwi["year"] = hwi["time"].dt.year
hwi = hwi.dropna(subset=["hwi"])

scenario_colors = {
    "observations": "black",
    "historical": "gray",
    "ssp126": "navy",
    "ssp245": "orange",
    "ssp370": "red",
}
level_colors = {"yellow": "gold", "orange": "darkorange", "red": "firebrick"}
scenarios = list(scenario_colors.keys())
levels = list(level_colors.keys())

# ========= Load HW days (optional) =========
try:
    hw = pd.read_csv(HW_CSV)
    hw = hw.dropna(subset=["heatwave_days"])
    hw["year"] = hw["year"].astype(int)
    have_hw = True
except Exception:
    hw = None
    have_hw = False

# ========= App =========
app = Dash(__name__)
server = app.server  # for gunicorn

app.layout = html.Div([
    html.H2("Latvija — ekstremālo karstuma rādītāji", style={"textAlign": "center"}),

    dcc.Tabs(id="tabs", value="hwi", children=[
        dcc.Tab(label="HWI (gads)", value="hwi"),
        dcc.Tab(label="Karstuma viļņu dienas (gads)", value="hw", disabled=not have_hw),
    ]),

    html.Div(id="controls-area", style={"margin": "12px 0"}),

    dcc.Graph(id="main-graph", config={"displaylogo": False})
])


# ======= Controls per tab =======
@app.callback(
    Output("controls-area", "children"),
    Input("tabs", "value")
)
def draw_controls(tab):
    if tab == "hwi":
        return html.Div([
            html.Div("Skats:", style={"marginBottom": "6px"}),
            dcc.RadioItems(
                id="hwi-view",
                options=[{"label": "Scenario", "value": "scenario"},
                         {"label": "Warning Level", "value": "warning"}],
                value="scenario",
                inline=True
            ),
            html.Div(style={"height": "10px"}),
            dcc.Dropdown(id="hwi-dd", style={"width": "320px"})
        ])
    else:
        return html.Div([
            html.Div("Scenāriji:", style={"marginBottom": "6px"}),
            dcc.Checklist(
                id="hw-scen",
                options=[{"label": s.upper() if s.startswith("ssp") else s, "value": s}
                         for s in ["obs", "historical", "ssp126", "ssp245", "ssp370"]],
                value=["obs", "historical", "ssp126", "ssp245", "ssp370"],
                inline=True
            )
        ])


# ======= Dropdown options for HWI tab =======
@app.callback(
    Output("hwi-dd", "options"),
    Output("hwi-dd", "value"),
    Input("hwi-view", "value"),
    prevent_initial_call=True
)
def hwi_dd(view):
    if view == "scenario":
        return [{"label": l.capitalize(), "value": l} for l in levels], "yellow"
    else:
        return [{"label": s.capitalize(), "value": s} for s in scenarios], "observations"


# ======= Main graph =======
@app.callback(
    Output("main-graph", "figure"),
    Input("tabs", "value"),
    Input("hwi-view", "value"),
    Input("hwi-dd", "value"),
    Input("hw-scen", "value")
)
def update_graph(tab, hwi_view, hwi_sel, hw_sel):
    # ---------- HWI TAB ----------
    if tab == "hwi":
        df = hwi.copy()
        fig = go.Figure()

        if hwi_view == "scenario":
            df = df[df["warning_level"] == hwi_sel]

            # Observations + historical
            for src in ["observations", "historical"]:
                sub = df[df["source"] == src].sort_values("year")
                if not sub.empty:
                    fig.add_trace(go.Scatter(
                        x=sub["year"],
                        y=sub["hwi"],
                        mode="lines+markers",
                        name=src,
                        marker=dict(color= scenario_colors[src]),
                        line=dict(color= scenario_colors[src]),
                        legendgroup=src
                    ))

            # SSP and conditional connectors to visible bases
            for ssp in ["ssp126", "ssp245", "ssp370"]:
                sub = df[df["source"] == ssp].sort_values("year")
                if sub.empty:
                    continue

                # SSP trace
                ssp_trace_name = ssp
                fig.add_trace(go.Scatter(
                    x=sub["year"], y=sub["hwi"],
                    mode="lines+markers",
                    name=ssp_trace_name,
                    marker=dict(color=scenario_colors[ssp]),
                    line=dict(color=scenario_colors[ssp]),
                    legendgroup=ssp
                ))

                # Connectors: only visible if both ends are visible
                for base in ["observations", "historical"]:
                    b = df[df["source"] == base].sort_values("year")
                    if b.empty:
                        continue
                    x0 = int(b["year"].max())
                    y0 = float(b[b["year"] == x0]["hwi"].iloc[0])
                    x1 = int(sub["year"].min())
                    y1 = float(sub[sub["year"] == x1]["hwi"].iloc[0])

                    # Make the connector "belong" to the ssp & base so it hides with either:
                    fig.add_trace(go.Scatter(
                        x=[x0, x1], y=[y0, y1],
                        mode="lines",
                        line=dict(color=scenario_colors[ssp], width=1.4),
                        hoverinfo="skip",
                        showlegend=False,
                        legendgroup=f"{ssp}__{base}",  # unique group
                        visible=True
                    ))

            fig.update_layout(
                title=f"HWI — {hwi_sel.capitalize()}",
                xaxis_title="Gads",
                yaxis_title="HWI"
            )

        else:
            # Warning-level view per scenario
            df = df[df["source"] == hwi_sel]
            for lvl, col in level_colors.items():
                sub = df[df["warning_level"] == lvl].sort_values("year")
                if sub.empty:
                    continue
                fig.add_trace(go.Scatter(
                    x=sub["year"], y=sub["hwi"],
                    mode="lines+markers",
                    name=lvl,
                    marker=dict(color=col),
                    line=dict(color=col),
                    legendgroup=lvl
                ))
            fig.update_layout(
                title=f"HWI — scenārijs: {hwi_sel}",
                xaxis_title="Gads",
                yaxis_title="HWI"
            )

        fig.update_layout(
            template="simple_white",
            hovermode="x unified",
            xaxis=dict(showgrid=True, gridcolor="lightgray"),
            yaxis=dict(showgrid=True, gridcolor="lightgray"),
            margin=dict(l=40, r=40, t=60, b=40),
            height=620,
            legend_title_text="",
            legend_groupclick="toggleitem"
        )
        return fig

    # ---------- HW DAYS TAB ----------
    else:
        df = hw.copy()
        fig = go.Figure()
        color_map = {"obs": "black", "historical": "gray", "ssp126": "navy", "ssp245": "orange", "ssp370": "red"}

        # Add scenario traces
        for scen in ["obs", "historical", "ssp126", "ssp245", "ssp370"]:
            if hw_sel and scen not in hw_sel:
                continue
            sub = df[df["scenario"] == scen].sort_values("year")
            if sub.empty:
                continue
            fig.add_trace(go.Scatter(
                x=sub["year"], y=sub["heatwave_days"],
                mode="lines+markers",
                name=scen,
                marker=dict(color=color_map[scen]),
                line=dict(color=color_map[scen]),
                legendgroup=scen
            ))

        # Add connectors that disappear if any endpoint is hidden
        def add_connector(src_a, src_b, ssp_name):
            a = df[df["scenario"] == src_a].sort_values("year")
            b = df[df["scenario"] == src_b].sort_values("year")
            s = df[df["scenario"] == ssp_name].sort_values("year")
            if a.empty or s.empty:
                return
            x0 = int(a["year"].max())
            y0 = float(a[a["year"] == x0]["heatwave_days"].iloc[0])
            x1 = int(s["year"].min())
            y1 = float(s[s["year"] == x1]["heatwave_days"].iloc[0])
            fig.add_trace(go.Scatter(
                x=[x0, x1], y=[y0, y1],
                mode="lines",
                line=dict(color=color_map[ssp_name], width=1.3),
                hoverinfo="skip",
                showlegend=False,
                legendgroup=f"{ssp_name}__{src_a}",
                visible=True
            ))

        if hw_sel:
            for ssp in ["ssp126", "ssp245", "ssp370"]:
                if ssp in hw_sel and "historical" in hw_sel:
                    add_connector("historical", ssp, ssp)
                if ssp in hw_sel and "obs" in hw_sel:
                    add_connector("obs", ssp, ssp)

        fig.update_layout(
            title="Karstuma viļņu dienas",
            xaxis_title="Gads",
            yaxis_title="Dienas",
            template="simple_white",
            hovermode="x unified",
            xaxis=dict(showgrid=True, gridcolor="lightgray"),
            yaxis=dict(showgrid=True, gridcolor="lightgray"),
            margin=dict(l=40, r=40, t=60, b=40),
            height=620,
            legend_title_text="",
            legend_groupclick="toggleitem"
        )
        return fig


if __name__ == "__main__":
    # prod-friendly defaults; PORT is used by Render/Heroku, etc.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8050)), debug=False)
