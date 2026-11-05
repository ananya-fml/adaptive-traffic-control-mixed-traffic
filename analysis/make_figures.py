"""Generate every figure in figures/ from the CSVs in data/ (no simulator needed).

    python analysis/make_figures.py

Each figure is written twice (``*_light.png`` and ``*_dark.png``) so the README
can serve the variant matching the reader's GitHub theme.

Sources
-------
data/derived/legacy_allocation_curve.csv  <- analysis/replay_legacy_controller.py
data/derived/run_identity.csv             <- analysis/audit_exports.py (private raw exports)
data/derived/comparisons.csv              <- analysis/audit_exports.py
data/derived/interval_network_delay.csv   <- analysis/audit_exports.py
data/derived/sumo_runs.csv                <- sumo/run_scenarios.py
data/reported/reported_results.csv        <- transcribed from the UG report and thesis
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
D, R, F = ROOT / "data" / "derived", ROOT / "data" / "reported", ROOT / "figures"

THEMES = {
    "light": dict(surface="#fcfcfb", text="#0b0b0b", text2="#52514e", grid="#e6e5e0",
                  s1="#2a78d6", s2="#eb6834", s3="#1baf7a", muted="#b9b8b2"),
    "dark": dict(surface="#1a1a19", text="#f0efec", text2="#c3c2b7", grid="#343432",
                 s1="#3987e5", s2="#d95926", s3="#199e70", muted="#5d5c58"),
}


def style(ax, t, ygrid=True, xgrid=False):
    ax.set_facecolor(t["surface"])
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(t["grid"])
    ax.tick_params(colors=t["text2"], labelsize=9, length=0)
    ax.yaxis.label.set_color(t["text2"])
    ax.xaxis.label.set_color(t["text2"])
    if ygrid:
        ax.yaxis.grid(True, color=t["grid"], lw=0.8)
    if xgrid:
        ax.xaxis.grid(True, color=t["grid"], lw=0.8)
    ax.set_axisbelow(True)


def new(t, w=8, h=4.2, **kw):
    fig, ax = plt.subplots(figsize=(w, h), facecolor=t["surface"], **kw)
    return fig, ax


def title(fig, t, main, sub):
    import textwrap
    w_in, h_in = fig.get_size_inches()
    fig.text(0.012, 1 - 0.1 / h_in, main, ha="left", va="top", fontsize=12.5, weight="bold", color=t["text"])
    wrapped = "\n".join(textwrap.wrap(sub, width=int(w_in * 14.2)))
    fig.text(0.012, 1 - 0.38 / h_in, wrapped, ha="left", va="top", fontsize=9, color=t["text2"],
             linespacing=1.35)


def save(fig, name, mode):
    F.mkdir(exist_ok=True)
    fig.savefig(F / f"{name}_{mode}.png", dpi=200, facecolor=fig.get_facecolor())
    plt.close(fig)


# 1 ---------------------------------------------------------------------------
def allocation(mode, t):
    c = pd.read_csv(D / "legacy_allocation_curve.csv")
    fig, ax = new(t, 8, 4.4)
    fig.subplots_adjust(left=0.08, right=0.80, top=0.78, bottom=0.13)
    ax.axhspan(67, 80, color=t["grid"], alpha=0.7, lw=0)
    ax.plot(c.ns_queue_share, c.ns_green_s, color=t["s1"], lw=2)
    ax.plot(c.ns_queue_share, c.ew_green_s, color=t["s2"], lw=2)
    ax.text(1.01, 80, "NS green", color=t["text"], fontsize=9, va="bottom", transform=ax.get_yaxis_transform())
    ax.text(1.01, 67, "EW green", color=t["text"], fontsize=9, va="top", transform=ax.get_yaxis_transform())
    ax.text(0.2, 73.5, "only 67–80 s\nis reachable", ha="center", va="center", fontsize=9, color=t["text2"])
    ax.axvspan(0.449, 0.551, color=t["s3"], alpha=0.12, lw=0)
    ax.text(0.5, 53, "proportional\nzone\n(45–55 %)", ha="center", fontsize=8.5, color=t["text2"])
    # decoded fixed-time programme (range reflects amber-placement ambiguity)
    for lo, hi, lab, col in ((60, 63, "fixed-time EW\n60–63 s", t["s2"]), (87, 93, "fixed-time NS\n87–93 s", t["s1"])):
        ax.add_patch(plt.Rectangle((1.04, lo), 0.03, hi - lo, color=col, alpha=0.55, lw=0, clip_on=False,
                                   transform=ax.transData))
        ax.text(1.09, (lo + hi) / 2, lab, fontsize=8.5, color=t["text2"], va="center", clip_on=False)
    ax.set_xlim(0, 1)
    ax.set_ylim(40, 100)
    ax.set_xlabel("NS share of smoothed queue  (NS / (NS + EW))")
    ax.set_ylabel("Green allocated (s)")
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    style(ax, t)
    title(fig, t, "The legacy split saturates at its 80 s cap",
          "Output of the unmodified proportional_split() (153 s cycle, 2×3 s amber, 10–80 s bounds). "
          "Deterministic logic, not simulation output.")
    save(fig, "legacy_allocation_response", mode)


# 2 ---------------------------------------------------------------------------
def run_identity(mode, t):
    ident = pd.read_csv(D / "run_identity.csv")
    ident = ident[ident.export == "vehicle_network"]
    scen = ["Base", "Encroach", "Lane_Block", "Monsoon", "Night"]
    fig, axes = plt.subplots(len(scen), 1, figsize=(8.6, 6.4), facecolor=t["surface"])
    fig.subplots_adjust(left=0.13, right=0.98, top=0.86, bottom=0.04, hspace=0.75)
    palette = [t["s1"], t["s2"], t["s3"]]
    for ax, sc in zip(axes, scen):
        g = ident[ident.scenario == sc]
        labels = sorted(g.distinct_output.unique(), key=lambda s: int(s.split("S")[-1]))
        cmap = {lab: palette[i] for i, lab in enumerate(labels)}
        for row, ctl in enumerate(["fixed", "adaptive"]):
            runs = g[g.controller == ctl].sort_values("simrun")
            for i, r in enumerate(runs.itertuples()):
                ax.add_patch(plt.Rectangle((i + 0.04, 1 - row + 0.08), 0.92, 0.84,
                                           color=cmap[r.distinct_output], lw=0))
                ax.text(i + 0.5, 1 - row + 0.5, f"{r.simrun}", ha="center", va="center", fontsize=8,
                        color="#ffffff", weight="bold")
            ax.text(-0.15, 1 - row + 0.5, ctl, ha="right", va="center", fontsize=9, color=t["text2"])
        ax.set_xlim(-0.05, 11.05)
        ax.set_ylim(0, 2)
        ax.axis("off")
        n = len(labels)
        ax.set_title(f"{sc.replace('_', '-')}  ·  {n} distinct output{'s' if n > 1 else ''} across "
                     f"{g.simrun.nunique()} run IDs", loc="left", fontsize=9.5, color=t["text"], pad=3)
    title(fig, t, "Most exported “replications” are the same simulation",
          "Each cell is one SIMRUN in the Vehicle Network Performance exports; equal colour = identical "
          "output (all columns except SIMRUN). Numbers are run IDs; colours are local to each scenario.")
    save(fig, "run_identity", mode)


# 3 ---------------------------------------------------------------------------
def reproduction(mode, t):
    c = pd.read_csv(D / "comparisons.csv")
    rep = pd.read_csv(R / "reported_results.csv")
    metrics = [("node_delay_movement_mean_s", "Node delay,\nmean of movements (unweighted)"),
               ("node_delay_vehweighted_s_per_veh", "Node delay,\nvehicle-weighted"),
               ("net_delay_mean_s_per_veh", "Network delay (DELAYAVG),\nmean of intervals")]
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.9), facecolor=t["surface"], sharey=True)
    fig.subplots_adjust(left=0.27, right=0.98, top=0.72, bottom=0.17, wspace=0.10)
    for ax, sc in zip(axes, ["Base", "Encroach"]):
        sub = c[(c.scenario == sc) & (c.pair_type == "report_figure_pair")].set_index("metric")
        reported = -float(rep[(rep.quantity == "delay_reduction") & (rep.scenario == sc)].value.iloc[0])
        ys = list(range(len(metrics)))[::-1]
        for y, (m, _) in zip(ys, metrics):
            v = sub.loc[m, "pct_change_adaptive_vs_fixed"]
            ax.plot([0, v], [y, y], color=t["muted"], lw=1.5, solid_capstyle="round")
            ax.plot(v, y, "o", ms=8, color=t["s1"], mec=t["surface"], mew=2)
            lab = f"{v:+.2f}%" if abs(v) < 0.05 else f"{v:+.1f}%"
            ax.text(v + (0.35 if v >= 0 else -0.35), y, lab, va="center",
                    ha="left" if v >= 0 else "right", fontsize=8.5, color=t["text"])
        ax.axvline(reported, color=t["s2"], lw=2, ls=(0, (4, 2)))
        ax.text(reported, len(metrics) - 0.35, f"reported {reported:+.1f}%", color=t["text"], fontsize=8.5,
                ha="center", va="bottom", bbox=dict(boxstyle="round,pad=0.25", fc=t["surface"], ec=t["s2"], lw=1))
        ax.axvline(0, color=t["text2"], lw=0.8)
        fr, ad = int(sub.fixed_simrun.iloc[0]), int(sub.adaptive_simrun.iloc[0])
        ax.set_title(f"{sc}  (run {fr} fixed vs run {ad} adaptive)", loc="left", fontsize=9.5, color=t["text"])
        ax.set_xlim(-9, 5)
        ax.set_ylim(-0.6, len(metrics) - 0.1)
        style(ax, t, ygrid=False, xgrid=True)
    fig.supxlabel("Adaptive vs fixed-time, % change in delay (negative = adaptive lower)", fontsize=9.5,
                  color=t["text2"], y=0.02, x=0.62)
    axes[0].set_yticks(list(range(len(metrics)))[::-1])
    axes[0].set_yticklabels([lab for _, lab in metrics], fontsize=9, color=t["text2"])
    title(fig, t, "Reported delay reductions vs what the recovered exports give",
          "Run pairs whose time series match the figures printed in the UG report and thesis. "
          "One simulation per controller (seed 42): descriptive only.")
    save(fig, "reproduction_check", mode)


# 4 ---------------------------------------------------------------------------
def timeseries(mode, t):
    s = pd.read_csv(D / "interval_network_delay.csv")
    pairs = [("Base", 3, 8), ("Encroach", 2, 4)]
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.9), facecolor=t["surface"], sharey=True)
    fig.subplots_adjust(left=0.07, right=0.98, top=0.70, bottom=0.15, wspace=0.12)
    for ax, (sc, rf, ra) in zip(axes, pairs):
        for ctl, run, col in (("fixed", rf, t["s1"]), ("adaptive", ra, t["s2"])):
            x = s[(s.scenario == sc) & (s.simrun == run) & (s.controller == ctl)].sort_values("interval")
            ax.plot(x.start_s / 60, x.delay_avg_s_per_veh, color=col, lw=1.6)
            yy = 1.02 if ctl == "adaptive" else 1.10
            ax.text(0.93, yy, f"{ctl} (run {run})", color=t["text"], fontsize=8.5, ha="right",
                    va="bottom", transform=ax.transAxes)
            ax.plot([0.945, 0.995], [yy + 0.03, yy + 0.03], color=col, lw=2.2, transform=ax.transAxes,
                    clip_on=False, solid_capstyle="round")
        ax.set_title(sc, loc="left", fontsize=9.5, color=t["text"])
        ax.set_xlabel("Simulation time (min), 60 s intervals")
        ax.set_xlim(10, 70)
        style(ax, t)
    axes[0].set_ylabel("Network mean delay (s/veh)")
    title(fig, t, "Recovered network-delay series behind the report figures",
          "VISSIM Vehicle Network Performance, DELAYAVG(ALL), 600–4,200 s. One run per controller, so "
          "differences cannot be separated from random variation.")
    save(fig, "network_delay_timeseries", mode)


# 5 ---------------------------------------------------------------------------
def sumo(mode, t):
    s = pd.read_csv(D / "sumo_runs.csv")
    s = s[s.exit_code == 0].copy()
    names = {"ug_fixed3_full": "UG package (Phase 5 fixed3)", "p5c_full": "Phase 5C, full demand",
             "p5c_reduced": "Phase 5C, reduced demand", "p5c_base_stable": "Phase 5C ‘base’",
             "p5c_encroachment": "Phase 5C ‘encroachment’"}
    s["label"] = [f"{names[r.run_id]}\n{r.demand_veh_per_h:,.0f} veh/h · {int(r.teleports)} teleports"
                  for r in s.itertuples()]
    s = s.iloc[::-1]
    fig, ax = new(t, 8.6, 4.0)
    fig.subplots_adjust(left=0.33, right=0.97, top=0.76, bottom=0.14)
    y = list(range(len(s)))
    ax.barh(y, s.inserted_share_of_loaded * 100, color=t["s1"], height=0.55)
    for yi, r in zip(y, s.itertuples()):
        v = r.inserted_share_of_loaded * 100
        inside = v > 85
        ax.text(v - 1.5 if inside else v + 1.5, yi, f"{v:.0f}%", va="center", ha="right" if inside else "left",
                fontsize=8.5, color="#ffffff" if inside else t["text"], weight="bold" if inside else "normal")
    ax.set_yticks(y)
    ax.set_yticklabels(s.label, fontsize=8.5, color=t["text2"])
    ax.set_xlim(0, 100)
    ax.set_xlabel("Vehicles that entered the network within 3,600 s (% of vehicles loaded)")
    style(ax, t, ygrid=False, xgrid=True)
    title(fig, t, "The SUMO networks run freely only at about a third of VISSIM demand",
          "SUMO 1.28, seed 42, one run each. VISSIM vehicle inputs total 8,520 veh/h. "
          "Source: sumo/run_scenarios.py → data/derived/sumo_runs.csv")
    save(fig, "sumo_operating_regimes", mode)


# 6 ---------------------------------------------------------------------------
def fixed_time_timing(mode, t):
    """Timing diagram of the archived 153 s fixed-time programme.

    Uses the reading adopted in the SUMO reconstruction (amber inside the green
    interval before each RED command): EW green 0-60, amber 60-63; NS green 63-150,
    amber 150-153. Alternative amber placement shifts each boundary by up to 3 s.
    """
    green, amber, red = ("#2e9e5b", "#f2b100", "#d64545") if mode == "light" else ("#36b06a", "#f5c02c", "#e05a5a")
    rows = [("SG1  East–West", [(0, 60, green, "green 60 s"), (60, 3, amber, ""), (63, 90, red, "red 90 s")]),
            ("SG2  North–South", [(0, 63, red, "red 63 s"), (63, 87, green, "green 87 s"), (150, 3, amber, "")])]
    fig, ax = new(t, 8.6, 2.9)
    fig.subplots_adjust(left=0.17, right=0.97, top=0.62, bottom=0.2)
    for i, (lab, segs) in enumerate(rows):
        y = 1 - i
        for x0, w, col, txt in segs:
            ax.barh(y, w, left=x0, height=0.5, color=col, edgecolor=t["surface"], linewidth=2)
            if txt:
                ax.text(x0 + w / 2, y, txt, ha="center", va="center", fontsize=9, color="#ffffff", weight="bold")
    ax.set_yticks([1, 0])
    ax.set_yticklabels([r[0] for r in rows], fontsize=9.5, color=t["text2"])
    ax.set_xlim(0, 153)
    ax.set_xticks([0, 30, 60, 90, 120, 153])
    ax.set_xlabel("Time in cycle (s)")
    style(ax, t, ygrid=False, xgrid=False)
    ax.text(61.5, 1.42, "amber 3 s", ha="center", fontsize=8.5, color=t["text2"])
    ax.text(151.5, 0.42, "amber 3 s", ha="right", fontsize=8.5, color=t["text2"])
    title(fig, t, "Fixed-time baseline: 153 s cycle, two stages, no all-red",
          "Decoded from the signal programme in the archived VISSIM models. Boundaries can shift by up to 3 s "
          "depending on how VISSIM places the fixed amber (EW green 60–63 s, NS 87–93 s).")
    save(fig, "fixed_time_timing", mode)


# 7 ---------------------------------------------------------------------------
def traci_results(mode, t):
    """Paired seed differences in mean delay from sumo/traci/run_traci_experiment.py."""
    path = D / "traci_paired.csv"
    if not path.exists():
        return
    p = pd.read_csv(path)
    p = p[p.metric == "mean_delay_s"]
    comps = [("adaptive_96 vs fixed_96", "Adaptive vs fixed-time\n(96 s, Phase 5C plan)"),
             ("adaptive_153 vs fixed_153", "Adaptive vs fixed-time\n(153 s, VISSIM plan)"),
             ("fixed_153 vs fixed_96", "Fixed 153 s vs\nfixed 96 s (reference)")]
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 3.9), facecolor=t["surface"], sharey=True)
    fig.subplots_adjust(left=0.24, right=0.98, top=0.72, bottom=0.17, wspace=0.10)
    for ax, sc in zip(axes, ["base", "encroachment"]):
        sub = p[p.scenario == sc].set_index("comparison")
        for y, (comp, _) in zip(range(len(comps))[::-1], comps):
            r = sub.loc[comp]
            col = t["s1"] if comp.startswith("adaptive") else t["muted"]
            ax.plot([r.ci95_low, r.ci95_high], [y, y], color=col, lw=2.2, solid_capstyle="round")
            ax.plot(r.mean_diff, y, "o", ms=8, color=col, mec=t["surface"], mew=2)
            ax.text(r.ci95_high + 0.6, y, f"{r.mean_diff:+.1f} s ({r["pct_change"]:+.0f}%)", va="center",
                    fontsize=8.5, color=t["text"])
        ax.axvline(0, color=t["text2"], lw=0.8)
        ax.set_title(f"{sc.capitalize()}  (n = {int(sub.n_seeds.iloc[0])} paired seeds)", loc="left",
                     fontsize=9.5, color=t["text"])
        lo, hi = p.ci95_low.min(), p.ci95_high.max()
        ax.set_xlim(min(lo, 0) - 2, max(hi, 0) + 24)
        style(ax, t, ygrid=False, xgrid=True)
    axes[0].set_yticks(range(len(comps))[::-1])
    axes[0].set_yticklabels([lab for _, lab in comps], fontsize=9, color=t["text2"])
    fig.supxlabel("Difference in mean delay per vehicle (s), mean and 95% CI; negative = first controller lower",
                  fontsize=9.5, color=t["text2"], y=0.02, x=0.6)
    title(fig, t, "SUMO/TraCI: queue-proportional vs fixed-time control",
          "New experiment (Nov 2026) on the Phase 5C network at its stable demand (~2,670 veh/h), Poisson arrivals. "
          "Not a re-run of the VISSIM study.")
    save(fig, "traci_delay_differences", mode)


def main():
    plt.rcParams.update({"font.family": "DejaVu Sans"})
    for mode, t in THEMES.items():
        allocation(mode, t)
        run_identity(mode, t)
        reproduction(mode, t)
        timeseries(mode, t)
        sumo(mode, t)
        fixed_time_timing(mode, t)
        traci_results(mode, t)
    print("figures written to", F)


if __name__ == "__main__":
    main()
