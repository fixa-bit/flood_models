"""Summarize saved Marala data without downloading or changing source values.

Produces a visual inventory, machine-readable inventory, and readable notes.
Daily record spacing is kept separate from a value's averaging/accumulation
period. An unconfirmed measurement period is never inferred from spacing.
"""
import argparse
import csv
import json
from datetime import date, datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Polygon, Rectangle


MODEL = Path(__file__).resolve().parents[1]
PROCESSED = MODEL / "processed/marala"
OUTPUT = PROCESSED / "metadata"
BLUE, TEAL, AMBER, PURPLE = "#2563a6", "#087f82", "#b56b08", "#7657a5"
INK, MUTED, RED = "#172b40", "#536779", "#ae342a"


def read_csv(relative):
    with (PROCESSED / relative).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(relative):
    return json.loads((PROCESSED / relative).read_text(encoding="utf-8-sig"))


def span(rows, key="date"):
    return min(row[key] for row in rows), max(row[key] for row in rows)


def build_inventory(as_of):
    wapda = read_csv("discharge/marala_daily_inflow_clean.csv")
    ffd_by_year = {
        year: read_csv(f"discharge/marala_ffd_{year}_bulletin_discharge.csv")
        for year in (2024, 2025, 2026)
    }
    ffd = [row for rows in ffd_by_year.values() for row in rows]
    irsa = read_csv("discharge/marala_irsa_daily_mean_discharge.csv")
    peaks = read_csv("discharge/marala_pmd_historical_flood_peaks.csv")
    rain = read_csv("rainfall/marala_catchment_daily_precipitation.csv")
    rain_valid = [row for row in rain if row["precipitation_mm_day"] != ""]
    cells = read_csv("rainfall/marala_rainfall_grid_cells.csv")
    basin = read_json("catchment/marala_upstream_catchment.geojson")
    audit = read_json("metadata/marala_feature_coverage_audit.json")
    area = basin["features"][0]["properties"]["area_km2_geodesic"]
    eligible = sum(row["eligible_daily_training"] == "1" for row in wapda)
    known_times = sum(bool(row["time_pakistan"]) for row in wapda)
    rain_dates = {row["date"] for row in rain_valid}
    paired = sum(row["eligible_daily_training"] == "1" and row["date"] in rain_dates for row in wapda)
    point = f"Marala river cross-section; upstream drainage approx. {area:,.0f} km2"

    def entry(feature, source, rows, value_count, footprint, interval, period, kind,
              units, quality, paths, date_key="date"):
        first, last = span(rows, date_key)
        return dict(feature=feature, source=source, records=len(rows), values=value_count,
                    unique_dates=len({row[date_key] for row in rows}), start=first, end=last,
                    spatial_footprint=footprint, record_interval=interval,
                    time_represented_by_one_value=period, value_type=kind, units=units,
                    quality=quality, local_files=paths)

    inventory = [
        entry("Inflow discharge", "WAPDA", wapda, len(wapda), point,
              "One dated record per day; continuous within saved span",
              "Historical measurement/averaging duration unconfirmed; 06:00 PKT confirmed only on 2024-12-19",
              "Dated discharge reading; neither instantaneous nor daily mean confirmed for full archive",
              "cusecs (ft3/s), with derived m3/s",
              f"{eligible:,} pass current date-level checks; {len(wapda)-eligible} withheld; {len(wapda)-known_times:,} times unconfirmed",
              ["discharge/marala_daily_inflow_clean.csv"]),
        entry("Inflow and outflow discharge", "FFD / PMD", ffd, len(ffd)*2, point,
              "Usually one bulletin per day during flood seasons; gaps and duplicate dates retained",
              "At 06:00 Pakistan time; instrument integration duration not stated",
              "Reported point-in-time snapshot; not a daily average",
              "1000 cusecs in source tables; cusecs in combined catalog",
              "Flood-season coverage only; archive/printed-date conflicts and duplicates require review",
              [f"discharge/marala_ffd_{year}_bulletin_discharge.csv" for year in ffd_by_year]),
        entry("Mean inflow and mean outflow", "IRSA", irsa, len(irsa)*2, point,
              "One report per day for the eight saved dates",
              "Daily averaging period; exact start/end clock times not published in saved reports",
              "Daily mean (average), kept separate from FFD snapshots",
              "cusecs (ft3/s)", "Only eight days collected; not a complete annual series",
              ["discharge/marala_irsa_daily_mean_discharge.csv"]),
        entry("Selected flood peak discharge", "PMD journal", peaks, len(peaks), point,
              "Selected flood events; no regular sampling interval",
              "Maximum within each selected event; event window and clock time unspecified",
              "Event maximum; not a daily average or continuous daily series",
              "1000 cusecs in source table",
              "Selected events only; do not join to daily observations as interchangeable values",
              ["discharge/marala_pmd_historical_flood_peaks.csv"], date_key="peak_date"),
        entry("Catchment precipitation", "NASA POWER", rain_valid, len(rain_valid),
              f"Full saved catchment: {area:,.3f} km2; {len(cells)} intersecting 0.5 x 0.625 degree native cells",
              "One catchment value per day",
              "24 hours: 00:00 to next 00:00 UTC = 05:00 to next 05:00 Pakistan time",
              "24-hour precipitation amount; spatial area-weighted mean across catchment; not instantaneous",
              "mm/day",
              "HOLD: unresolved request-period-dependent source discrepancy; 2026-10-22 requested but missing",
              ["rainfall/marala_catchment_daily_precipitation.csv"]),
        dict(feature="Upstream catchment boundary", source="Global Watersheds / MERIT",
             records=1, values=1, unique_dates=0, start="", end="",
             spatial_footprint=f"{area:,.3f} km2 upstream of Marala; 74.05041-77.80625 E, 32.08875-34.21208 N",
             record_interval="Static geometry; not a time series",
             time_represented_by_one_value="Not applicable; no daily observation period",
             value_type="Static research delineation; nominal source raster about 90 m at equator",
             units="WGS84 geometry / km2",
             quality="Nine source/geometry checks passed; not agency-certified or field-surveyed",
             local_files=["catchment/marala_upstream_catchment.geojson"]),
    ]
    summary = {
        "inventory_date_pakistan": as_of,
        "scope": "Existing saved Marala files only; no new source downloads or corrections",
        "source_snapshot_note": "Latest saved source collections and scientific audit are dated 2026-10-23",
        "features": inventory,
        "combined_discharge_measurement_rows": len(read_csv("discharge/marala_discharge_all_sources.csv")),
        "eligible_discharge_dates": eligible,
        "wapda_confirmed_time_dates": known_times,
        "rainfall_calendar_rows": len(rain),
        "rainfall_nonmissing_days": len(rain_valid),
        "rainfall_missing_dates": [row["date"] for row in rain if row["precipitation_mm_day"] == ""],
        "rainfall_source_cell_rows": sum(int(row["required_grid_cells"]) for row in rain),
        "rainfall_nonmissing_source_cell_values": sum(int(row["valid_grid_cells"]) for row in rain),
        "rainfall_grid_cells": len(cells),
        "catchment_area_km2": area,
        "ffd_by_year": {str(year): {"records": len(rows), "unique_dates": len({r["date"] for r in rows}),
                                  "start": span(rows)[0], "end": span(rows)[1]}
                        for year, rows in ffd_by_year.items()},
        "date_overlap": {"start": span(wapda)[0], "end": span(wapda)[1],
                         "all_wapda_dates_have_nonmissing_precipitation": all(row["date"] in rain_dates for row in wapda),
                         "eligible_date_pairs": paired,
                         "does_not_prove_matching_observation_intervals_or_issue_time_availability": True},
        "rainfall_training_hold": audit["rainfall_quality_blocked"],
        "rainfall_audit_file": "metadata/marala_feature_coverage_audit.json",
        "not_collected": {key: value for key, value in audit["other_features"].items()
                          if value.startswith("not collected")},
        "counting_note": "Sources overlap; inflow/outflow are different variables. Do not sum source rows as unique daily training examples. Source-cell rainfall and catchment rainfall are two representations of the same precipitation feature.",
    }
    return summary, wapda, ffd_by_year, irsa, rain_valid, basin


def draw_geometry(axis, geometry, **kwargs):
    parts = geometry["coordinates"]
    if geometry["type"] == "Polygon":
        parts = [parts]
    for polygon in parts:
        axis.add_patch(Polygon(polygon[0], **kwargs))
        # Keep polygon holes unfilled; none are needed for the saved boundary.
        for hole in polygon[1:]:
            axis.add_patch(Polygon(hole, facecolor="white", edgecolor="none", zorder=4))


def draw_chart(summary, wapda, ffd_by_year, irsa, rain, basin, stem):
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                         "text.color": INK, "axes.labelcolor": MUTED,
                         "xtick.color": MUTED, "ytick.color": INK,
                         "pdf.fonttype": 42})
    fig = plt.figure(figsize=(21, 15), facecolor="white")
    fig.text(.035, .965, "MARALA | What data is actually saved?", fontsize=25, weight="bold")
    fig.text(.035, .935, f"Inventory: {summary['inventory_date_pakistan']}  |  Saved source snapshot: 23 Oct 2026  |  Historical data, not forecasts", fontsize=12, color=MUTED)
    metrics = [
        (f"{len(wapda):,} daily inflow records", f"WAPDA: {summary['eligible_discharge_dates']:,} pass current checks; {len(wapda)-summary['eligible_discharge_dates']} withheld", BLUE),
        (f"{len(rain):,} daily precipitation values", f"{summary['rainfall_grid_cells']} catchment cells; rainfall remains on HOLD", AMBER),
        (f"{summary['catchment_area_km2']:,.0f} km² upstream catchment", "100% geometric grid coverage; research boundary", TEAL),
    ]
    for x, (title, detail, color) in zip((.035, .36, .685), metrics):
        fig.add_artist(Rectangle((x, .848), .29, .06, transform=fig.transFigure,
                                 facecolor="#f3f7fa", edgecolor="none"))
        fig.text(x+.011, .881, title, fontsize=16, weight="bold", color=color)
        fig.text(x+.011, .858, detail, fontsize=10.2, color=MUTED)

    ax = fig.add_axes([.13, .564, .44, .235])
    ax.set_title("WHEN THE SAVED DAILY RECORDS EXIST", loc="left", fontsize=13, weight="bold", pad=18)
    datasets = [("WAPDA inflow", wapda, BLUE),
                *[(f"FFD {year}: in + out", rows, PURPLE) for year, rows in ffd_by_year.items()],
                ("IRSA daily means", irsa, BLUE), ("Precipitation", rain, AMBER)]
    for y, (label, rows, color) in enumerate(datasets):
        day_values = sorted({date.fromisoformat(row["date"]) for row in rows})
        # One vertical segment per actual saved date; gaps remain visible.
        ax.vlines(day_values, y-.22, y+.22, color=color, lw=1.7)
        suffix = f"{len(rows):,} records"
        if label == "Precipitation":
            suffix = f"{len(rows):,} nonmissing days"
        ax.text(1.012, y, suffix, transform=ax.get_yaxis_transform(), fontsize=10.5, va="center", color=color)
    withheld = [date.fromisoformat(row["date"]) for row in wapda if row["eligible_daily_training"] != "1"]
    ax.scatter(withheld, [0]*len(withheld), marker="|", s=180, color=RED, zorder=5)
    ax.set_yticks(range(len(datasets)), [row[0] for row in datasets], fontsize=11)
    ax.set_ylim(len(datasets)-.45, -.7)
    ax.set_xlim(datetime(2016, 1, 1), datetime(2026, 12, 31))
    ax.xaxis.set_major_locator(mdates.YearLocator(2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.grid(axis="x", color="#dfe7ed", lw=.8)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(axis="y", length=0, pad=12)
    fig.text(.13, .523, "FFD bars cover flood seasons only. Red ticks: 7 withheld WAPDA dates.\nPMD's 30 selected event peaks (1970–2016) are listed below; they are not a daily series.", fontsize=10.5, color=MUTED, linespacing=1.5)

    geo = fig.add_axes([.745, .559, .225, .247])
    geo.set_title("WHERE ONE VALUE APPLIES", loc="left", fontsize=13, weight="bold", pad=13)
    footprints = read_json("catchment/marala_rainfall_grid_footprints.geojson")
    clipped = read_json("rainfall/marala_rainfall_catchment_cells.geojson")
    for feature in footprints["features"]:
        draw_geometry(geo, feature["geometry"], facecolor="#f5fafb", edgecolor="#8eafb8", lw=.7, zorder=1)
    for feature in clipped["features"]:
        draw_geometry(geo, feature["geometry"], facecolor="#b2ddd4", edgecolor="#6eaaa0", lw=.6, zorder=2)
    for feature in basin["features"]:
        draw_geometry(geo, feature["geometry"], facecolor="none", edgecolor=TEAL, lw=1.4, zorder=5)
    geo.scatter([74.46], [32.67], s=75, color=BLUE, edgecolors="white", zorder=7)
    geo.annotate("Marala discharge\nreported here", (74.46, 32.67), xytext=(74.04, 31.78),
                 fontsize=9, color=BLUE, arrowprops={"arrowstyle": "->", "color": BLUE}, zorder=8)
    geo.set_xlim(73.72, 77.95)
    geo.set_ylim(31.64, 34.46)
    geo.set_aspect(1 / .84)
    geo.set_xlabel("Longitude (°E)", fontsize=9)
    geo.set_ylabel("Latitude (°N)", fontsize=9)
    geo.tick_params(labelsize=9)
    geo.grid(color="#e1e8ec", alpha=.6, lw=.5)
    geo.legend(handles=[Patch(facecolor="#b2ddd4", edgecolor=TEAL, label="Precipitation: area-weighted basin"),
                        Line2D([], [], color=BLUE, marker="o", lw=0, label="Discharge: river cross-section")],
               loc="lower left", bbox_to_anchor=(-.03, -.36), frameon=False, fontsize=9)

    table_ax = fig.add_axes([.035, .166, .94, .30])
    table_ax.axis("off")
    table_ax.set_title("WHAT ONE SAVED VALUE MEANS", loc="left", fontsize=13, weight="bold", pad=16)
    e = summary["features"]
    table_rows = [
        ["Inflow discharge\nWAPDA", f"{e[0]['records']:,} dates; {summary['eligible_discharge_dates']:,} pass QC\n01 Mar 2016–19 Dec 2024", "Marala river cross-section\n(outlet of ~28,781 km² basin)", "1 record / day", "Duration NOT confirmed\nOnly 19 Dec 2024: 06:00 PKT", "Unconfirmed:\ninstantaneous vs mean"],
        ["Inflow + outflow\nFFD / PMD", f"{e[1]['records']:,} bulletins; {e[1]['unique_dates']} unique dates\nFlood seasons 2024, 2025, 2026", "Marala river cross-section\nTwo separate flow variables", "Usually daily\nSeasonal + gaps", "At 06:00 PKT\nInstrument integration unstated", "Point-in-time snapshot\nNot a daily average"],
        ["Mean in + outflow\nIRSA", f"{e[2]['records']} reports / {e[2]['values']} flow values\n16–23 Oct 2026", "Marala river cross-section\nTwo separate mean flows", "1 report / day", "Daily averaging period\nExact clock bounds unknown", "Daily average"],
        ["Flood peaks\nPMD journal", f"{e[3]['records']} selected events\n02 Jul 1970–07 Aug 2016", "Marala river cross-section", "Selected events\nIrregular", "Each event's maximum\nEvent window / time unspecified", "Maximum\nNot a daily average"],
        ["Precipitation\nNASA POWER", f"{e[4]['records']:,} nonmissing days\n01 Mar 2016–21 Oct 2026", "Full ~28,781 km² catchment\n21 cells: 0.5° × 0.625°", "1 value / day", "24 hours: 00:00–00:00 UTC\n05:00–next 05:00 PKT", "24-hour precipitation amount\nAREA-weighted average; HOLD"],
        ["Catchment boundary\nGlobal Watersheds / MERIT", "1 saved upstream polygon\nSource/geometry checks: 23 Oct 2026", "28,780.646 km²\nIncludes cross-border headwaters", "Static\nNo daily readings", "No observation time window", "Static research geometry\nNot agency-certified"],
    ]
    headers = ["FEATURE / SOURCE", "SAVED AMOUNT / HISTORY", "SPATIAL FOOTPRINT", "RECORD INTERVAL", "TIME REPRESENTED BY ONE VALUE", "VALUE TYPE"]
    table = table_ax.table(cellText=table_rows, colLabels=headers,
                          colWidths=[.15, .21, .19, .12, .19, .18],
                          bbox=[0, 0, 1, 1], cellLoc="left", colLoc="left")
    table.auto_set_font_size(False)
    table.set_fontsize(10.5)
    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor("white")
        cell.PAD = .08
        if row == 0:
            cell.set_facecolor(INK)
            cell.set_text_props(color="white", weight="bold", fontsize=9)
        else:
            cell.set_facecolor("#fff3df" if row == 5 else ("#f1f6f9" if row % 2 else "#f9fbfc"))
            cell.set_text_props(color=INK)
            if col == 0:
                cell.set_text_props(weight="bold")
    for col in range(len(headers)):
        table[(0, col)].set_height(table[(1, 0)].get_height()*.7)

    fig.add_artist(Rectangle((.035, .082), .94, .063, transform=fig.transFigure,
                             facecolor="#fff1e8", edgecolor="#f0c5a3"))
    fig.text(.045, .121, "RAINFALL TRAINING HOLD", fontsize=12, weight="bold", color=RED)
    fig.text(.045, .099, "Saved values disagree with independent daily/hourly checks on sampled dates. Matching date coverage does not make rainfall ready for training.", fontsize=11)
    fig.text(.035, .055, f"DATE OVERLAP: 01 Mar 2016–19 Dec 2024; all {len(wapda):,} WAPDA dates have saved precipitation. {summary['date_overlap']['eligible_date_pairs']:,} pairs pass the discharge/date checks only.", fontsize=10.5)
    fig.text(.035, .032, "NOT YET COLLECTED: temperature, snow, soil moisture, soil properties, reservoir operations, and archived future-weather forecasts.", fontsize=10.5, color=MUTED)
    fig.text(.035, .014, "Spacing between records ≠ averaging duration. Spatial coverage ≠ measurement accuracy. Unknown historical reading times remain unknown. Map: WGS84 research footprint; no political boundaries shown.", fontsize=9, color=MUTED)
    fig.savefig(stem.with_suffix(".png"), dpi=160, facecolor="white")
    fig.savefig(stem.with_suffix(".pdf"), facecolor="white")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", required=True, type=date.fromisoformat,
                        help="Inventory date in Pakistan, YYYY-MM-DD; source coverage is read from saved files")
    args = parser.parse_args()
    summary, wapda, ffd_by_year, irsa, rain, basin = build_inventory(args.as_of.isoformat())
    OUTPUT.mkdir(parents=True, exist_ok=True)
    stem = OUTPUT / f"marala_data_inventory_{args.as_of.isoformat()}"
    stem.with_suffix(".json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    with stem.with_suffix(".csv").open("w", encoding="utf-8", newline="") as handle:
        fields = list(summary["features"][0])
        writer = csv.DictWriter(handle, fields)
        writer.writeheader()
        for row in summary["features"]:
            writer.writerow({**row, "local_files": "; ".join(row["local_files"])})
    draw_chart(summary, wapda, ffd_by_year, irsa, rain, basin, stem)
    lines = [f"# Marala saved-data inventory — {args.as_of}", "",
             "Based on the saved files; latest collection/audit snapshot is 2026-10-23. No new source data was downloaded.", "",
             f"![Visual inventory]({stem.name}.png)", "",
             "Record interval means spacing between saved observations. It does not establish the time period averaged or accumulated into one value.", "",
             "| Feature / source | Saved amount and history | Area represented | Record interval | Time represented by one value | Type / limitation |",
             "|---|---|---|---|---|---|"]
    for row in summary["features"]:
        history = f"{row['records']:,} records; {row['start']} to {row['end']}" if row["start"] else "1 static geometry"
        lines.append(f"| {row['feature']} / {row['source']} | {history} | {row['spatial_footprint']} | {row['record_interval']} | {row['time_represented_by_one_value']} | {row['value_type']}; {row['quality']} |")
    lines += ["", f"The combined discharge catalog has {summary['combined_discharge_measurement_rows']:,} measurement rows. These are overlapping source records, two different flow variables, averages and event peaks; they are not that many unique training days.", "",
              f"Precipitation has {summary['rainfall_nonmissing_days']:,} nonmissing catchment days and {summary['rainfall_nonmissing_source_cell_values']:,} nonmissing cell-day values across 21 cells. The requested 2026-10-22 date remains blank (21 missing source-cell values).", "",
              f"The common saved-date interval is 2016-03-01 to 2024-12-19. All 3,216 WAPDA dates have a saved precipitation value; {summary['date_overlap']['eligible_date_pairs']:,} date pairs pass the existing discharge checks. This does not resolve observation-time alignment or rainfall accuracy.", "",
              "**Rainfall remains on hold for training.** Saved long-period NASA values disagree with shorter-period daily/hourly checks on sampled dates. Originals and evidence are retained; no blanket scaling correction has been applied. See [the scientific audit](marala_feature_coverage_audit.json).", "",
              "Temperature, snow, soil moisture, soil properties, reservoir operations and archived future-weather forecasts have not been collected.", "",
              "Source tables: [WAPDA](../discharge/marala_daily_inflow_clean.csv), [FFD 2024](../discharge/marala_ffd_2024_bulletin_discharge.csv), [FFD 2025](../discharge/marala_ffd_2025_bulletin_discharge.csv), [FFD 2026](../discharge/marala_ffd_2026_bulletin_discharge.csv), [IRSA](../discharge/marala_irsa_daily_mean_discharge.csv), [PMD peaks](../discharge/marala_pmd_historical_flood_peaks.csv), [precipitation](../rainfall/marala_catchment_daily_precipitation.csv), [boundary](../catchment/marala_upstream_catchment.geojson). Exact publication URLs remain in those source tables and receipts.", "",
              "Map attribution: Heberger (2022), Global Watersheds; Yamazaki et al. (2019), MERIT Hydro; Lin et al. (2019), MERIT-Basins. Derived boundary terms: CC BY-NC-SA 4.0; see [catchment notes](../catchment/README.md).", ""]
    stem.with_suffix(".md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"inventory": str(stem), "wapda_records": len(wapda), "eligible_discharge_dates": summary["eligible_discharge_dates"],
                      "ffd_bulletins": sum(len(rows) for rows in ffd_by_year.values()), "rainfall_days": len(rain),
                      "rainfall_hold": summary["rainfall_training_hold"]}, indent=2))


if __name__ == "__main__":
    main()
