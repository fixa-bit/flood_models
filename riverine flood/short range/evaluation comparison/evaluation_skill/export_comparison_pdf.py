"""Export the flood/non-flood markdown comparison as a compact landscape PDF."""

import argparse
from pathlib import Path


def pdf_text(x: float, y: float, value: str, font: str = "F1", size: float = 9, color="0 0 0") -> str:
    value = value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return f"{color} rg BT /{font} {size} Tf 1 0 0 1 {x:.1f} {y:.1f} Tm ({value}) Tj ET\n"


def split_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def make_pdf(markdown: Path, output: Path) -> None:
    lines = markdown.read_text(encoding="utf-8").splitlines()
    threshold = next((line.split("**")[1] for line in lines if "Flood threshold:" in line), "not specified")
    cases = next((line.split("**")[1] for line in lines if "Common observed cases:" in line), "not specified")
    table_index = next(i for i, line in enumerate(lines) if line.startswith("| Model | Actual class |"))
    rows = []
    for line in lines[table_index + 2:]:
        if not line.startswith("|"):
            break
        rows.append(split_row(line))
    if len(rows) == 0:
        raise ValueError("No comparison rows found in markdown input")

    page_w, page_h = 842, 650
    margin_x = 58
    widths = [174, 80, 42, 66, 66, 66, 52, 90, 90]
    headers = ["Model", "Actual class", "n", "Accuracy", "Precision", "Recall", "F1", "RMSE (m3/s)", "MAE (m3/s)"]
    commands = []
    commands.append("0.07 0.18 0.32 rg 0 0 842 595 re f\n")
    commands.append("1 1 1 rg 20 20 802 610 re f\n")
    commands.append(pdf_text(48, 603, "30-DAY FLOOD FORECAST MODEL COMPARISON", "F2", 17, "0.07 0.18 0.32"))
    commands.append(pdf_text(48, 583, "Lead-30 classification scores and discharge errors on matched observed targets", "F1", 10, "0.25 0.31 0.39"))

    cards = [(48, "COMMON TEST DAYS", cases), (306, "FLOOD DEFINITION", f"Training Q95: {threshold} m3/s"), (564, "EVALUATION", "Lead day 30")]
    for x, title, value in cards:
        commands.append(f"0.94 0.96 0.98 rg {x} 531 230 37 re f\n")
        commands.append(pdf_text(x + 10, 553, title, "F2", 7.5, "0.25 0.31 0.39"))
        commands.append(pdf_text(x + 10, 539, value, "F2", 10, "0.07 0.18 0.32"))

    table_top = 513
    header_h = 31
    row_h = 17
    x = margin_x
    commands.append(f"0.07 0.18 0.32 rg {margin_x} {table_top-header_h} {sum(widths)} {header_h} re f\n")
    for header, width in zip(headers, widths):
        commands.append(pdf_text(x + 7, table_top - 20, header, "F2", 8, "1 1 1"))
        x += width

    for idx, row in enumerate(rows):
        y = table_top - header_h - (idx + 1) * row_h
        actual_class = row[1]
        if actual_class == "Flood":
            fill = "1.00 0.94 0.92"
        else:
            fill = "0.92 0.96 0.99"
        commands.append(f"{fill} rg {margin_x} {y} {sum(widths)} {row_h} re f\n")
        commands.append(f"0.82 0.86 0.90 RG {margin_x} {y} m {margin_x+sum(widths)} {y} l S\n")
        x = margin_x
        for col, (cell, width) in enumerate(zip(row, widths)):
            if col < 2:
                commands.append(pdf_text(x + 7, y + 5, cell, "F2" if col == 0 else "F1", 7.5))
            else:
                commands.append(pdf_text(x + 5, y + 5, cell, "F1", 7.5))
            x += width

    commands.append("0.96 0.97 0.98 rg 48 26 746 40 re f\n")
    commands.append(pdf_text(60, 52, "Accuracy uses both classes; precision, recall and F1 are class-specific. RMSE is flow error within the class shown.", "F1", 8))
    commands.append(pdf_text(60, 39, "Retrospective observed test (2022-2024); reanalysis proxy inputs, not operational forecast skill. Flood threshold: training Q95.", "F1", 8))
    commands.append(pdf_text(48, 13, "Flood recall is useful for missed high-flow days; only 51 of 1,055 common targets are floods.", "F1", 8, "0.30 0.35 0.42"))

    stream = "".join(commands).encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_w} {page_h}] /Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>".encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"endstream",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{number} 0 obj\n".encode())
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects)+1}\n".encode())
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(pdf)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("markdown", type=Path, help="Comparison report produced by compare_models.py")
    parser.add_argument("output", type=Path, help="Destination PDF path")
    args = parser.parse_args()
    make_pdf(args.markdown, args.output)
    print(f"Saved PDF: {args.output}")


if __name__ == "__main__":
    main()
