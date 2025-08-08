import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, dcc, html, Input, Output

# ====== HWI ======
hwi = pd.read_csv("./LV_average_HWI.csv", parse_dates=["time"])
hwi["year"] = hwi["time"].dt.year
hwi = hwi.dropna(subset=["hwi"])

scenario_colors = {
    "observations": "black",
    "historical": "gray",
    "ssp126": "navy",
    "ssp245": "orange",
    "ssp370": "red",
}
level_colors = {"yellow":"gold","orange":"darkorange","red":"firebrick"}
scenarios = list(scenario_colors.keys())
levels = list(level_colors.keys())

# ====== HW days (ja lietosi) ======
try:
    hw = pd.read_csv("./LV_average_HWdays.csv")
    hw = hw.dropna(subset=["heatwave_days"])
    hw["year"] = hw["year"].astype(int)
    have_hw = True
except Exception:
    have_hw = False

app = Dash(__name__)
server = app.server  # <- svarīgi hostēšanai

app.layout = html.Div([
    html.H2("Latvija — ekstremālo karstuma rādītāji"),
    dcc.Tabs(id="tabs", value="hwi", children=[
        dcc.Tab(label="HWI (gads)", value="hwi"),
        dcc.Tab(label="Karstuma viļņu dienas (gads)", value="hw", disabled=not have_hw),
    ]),

    html.Div(id="controls-area"),

    dcc.Graph(id="main-graph")
])

@app.callback(
    Output("controls-area", "children"),
    Input("tabs", "value")
)
def draw_controls(tab):
    if tab == "hwi":
        return html.Div([
            dcc.RadioItems(
                id="hwi-view",
                options=[{"label":"Scenario", "value":"scenario"},
                         {"label":"Warning Level", "value":"warning"}],
                value="scenario",
                inline=True
            ),
            dcc.Dropdown(id="hwi-dd", style={"width":"40%"})
        ])
    else:
        return html.Div([
            dcc.Checklist(
                id="hw-scen",
                options=[{"label": s.upper() if s.startswith("ssp") else s, "value": s}
                         for s in ["obs","historical","ssp126","ssp245","ssp370"]],
                value=["obs","historical","ssp126","ssp245","ssp370"],
                inline=True
            )
        ])

@app.callback(
    Output("hwi-dd","options"),
    Output("hwi-dd","value"),
    Input("hwi-view","value"),
    prevent_initial_call=True
)
def hwi_dd(view):
    if view == "scenario":
        return [{"label": l.capitalize(), "value": l} for l in levels], "yellow"
    else:
        return [{"label": s.capitalize(), "value": s} for s in scenarios], "observations"

@app.callback(
    Output("main-graph","figure"),
    Input("tabs","value"),
    Input("hwi-view","value"),
    Input("hwi-dd","value"),
    Input("hw-scen","value")
)
def update_graph(tab, hwi_view, hwi_sel, hw_sel):
    if tab == "hwi":
        df = hwi.copy()
        fig = go.Figure()
        if hwi_view == "scenario":
            df = df[df["warning_level"] == hwi_sel]
            # lines for observations + historical
            for src in ["observations","historical"]:
                sub = df[df["source"]==src]
                if not sub.empty:
                    fig.add_trace(go.Scatter(
                        x=sub["year"], y=sub["hwi"],
                        mode="lines+markers", name=src,
                        marker=dict(color=scenario_colors[src]),
                        line=dict(color=scenario_colors[src])
                    ))
            # ssp + connectors
            for ssp in ["ssp126","ssp245","ssp370"]:
                sub = df[df["source"]==ssp]
                if sub.empty: continue
                fig.add_trace(go.Scatter(
                    x=sub["year"], y=sub["hwi"],
                    mode="lines+markers", name=ssp,
                    marker=dict(color=scenario_colors[ssp]),
                    line=dict(color=scenario_colors[ssp])
                ))
                # connectors appear only if both ends are present
                for base in ["observations","historical"]:
                    b = df[df["source"]==base]
                    if b.empty: continue
                    fig.add_trace(go.Scatter(
                        x=[b["year"].max(), sub["year"].min()],
                        y=[b.sort_values("year")["hwi"].iloc[-1], sub.sort_values("year")["hwi"].iloc[0]],
                        mode="lines",
                        line=dict(color=scenario_colors[ssp], width=1.3, dash="solid"),
                        hoverinfo="skip",
                        showlegend=False,
                        legendgroup=ssp
                    ))
            fig.update_layout(title=f"HWI — {hwi_sel.capitalize()}", xaxis_title="Gads", yaxis_title="HWI")

        else:
            df = df[df["source"] == hwi_sel]
            for lvl, col in level_colors.items():
                sub = df[df["warning_level"]==lvl]
                if sub.empty: continue
                fig.add_trace(go.Scatter(
                    x=sub["year"], y=sub["hwi"],
                    mode="lines+markers", name=lvl,
                    marker=dict(color=col), line=dict(color=col)
                ))
            fig.update_layout(title=f"HWI — scenārijs: {hwi_sel}", xaxis_title="Gads", yaxis_title="HWI")

        fig.update_layout(template="simple_white", hovermode="x unified",
                          xaxis=dict(showgrid=True, gridcolor="lightgray"),
                          yaxis=dict(showgrid=True, gridcolor="lightgray"))
        return fig

    # ---- HW days tab ----
    else:
        df = hw.copy()
        fig = go.Figure()
        color_map = {"obs":"black","historical":"gray","ssp126":"navy","ssp245":"orange","ssp370":"red"}
        # selected scenarios
        for scen in ["obs","historical","ssp126","ssp245","ssp370"]:
            if hw_sel and scen not in hw_sel: continue
            sub = df[df["scenario"]==scen]
            if sub.empty: continue
            fig.add_trace(go.Scatter(
                x=sub["year"], y=sub["heatwave_days"],
                mode="lines+markers", name=scen,
                marker=dict(color=color_map[scen]), line=dict(color=color_map[scen])
            ))
        # connectors appear automatically because we only draw them if both traces are present
        if hw_sel and "historical" in hw_sel:
            hist = df[df["scenario"]=="historical"].sort_values("year")
            for ssp in ["ssp126","ssp245","ssp370"]:
                if not (hw_sel and ssp in hw_sel): continue
                s = df[df["scenario"]==ssp].sort_values("year")
                if hist.empty or s.empty: continue
                fig.add_trace(go.Scatter(
                    x=[hist["year"].max(), s["year"].min()],
                    y=[hist["heatwave_days"].iloc[-1], s["heatwave_days"].iloc[0]],
                    mode="lines", line=dict(color=color_map[ssp], width=1.3), hoverinfo="skip",
                    showlegend=False, legendgroup=ssp
                ))
        if hw_sel and "obs" in hw_sel:
            obs = df[df["scenario"]=="obs"].sort_values("year")
            for ssp in ["ssp126","ssp245","ssp370"]:
                if not (hw_sel and ssp in hw_sel): continue
                s = df[df["scenario"]==ssp].sort_values("year")
                if obs.empty or s.empty: continue
                fig.add_trace(go.Scatter(
                    x=[obs["year"].max(), s["year"].min()],
                    y=[obs["heatwave_days"].iloc[-1], s["heatwave_days"].iloc[0]],
                    mode="lines", line=dict(color=color_map[ssp], width=1.3, dash="solid"),
                    hoverinfo="skip", showlegend=False, legendgroup=ssp
                ))
        fig.update_layout(title="Karstuma viļņu dienas", xaxis_title="Gads", yaxis_title="Dienas",
                          template="simple_white", hovermode="x unified",
                          xaxis=dict(showgrid=True, gridcolor="lightgray"),
                          yaxis=dict(showgrid=True, gridcolor="lightgray"))
        return fig

if __name__ == "__main__":
    app.run(debug=True)
