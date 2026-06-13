from __future__ import annotations

import os
import re
import shutil
import subprocess
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
FIGURES = ROOT / "artifacts" / "visualizations"
OUTPUT = DOCS / "overleaf"
TEMPLATE = ROOT / "tools" / "overleaf_template.tex"
BUILD = ROOT / ".qa_overleaf_build"

FIGURE_NAMES = [
    "01_architektura.png",
    "02_przykladowe_szeregi.png",
    "03_prognoza_vs_rzeczywistosc.png",
    "04_blad_prognozy.png",
    "05_model_vs_naiwny.png",
    "06_sterowania_mpc.png",
    "07_petla_zamknieta.png",
]


def find_pandoc() -> Path:
    executable = shutil.which("pandoc")
    if executable:
        return Path(executable)

    package_root = Path(os.environ["LOCALAPPDATA"]) / "Microsoft" / "WinGet" / "Packages"
    matches = list(package_root.glob("JohnMacFarlane.Pandoc_*/pandoc-*/pandoc.exe"))
    if not matches:
        raise FileNotFoundError("Pandoc was not found.")
    return matches[0]


def find_pdflatex() -> Path:
    executable = shutil.which("pdflatex")
    if executable:
        return Path(executable)

    candidate = (
        Path(os.environ["LOCALAPPDATA"])
        / "Programs"
        / "MiKTeX"
        / "miktex"
        / "bin"
        / "x64"
        / "pdflatex.exe"
    )
    if not candidate.exists():
        raise FileNotFoundError("pdfLaTeX was not found.")
    return candidate


def run(command: list[str], cwd: Path | None = None) -> None:
    result = subprocess.run(
        command,
        cwd=cwd or ROOT,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        raise RuntimeError(f"Command failed with exit code {result.returncode}: {command}")


def reset_directory(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def copy_figures(project: Path) -> None:
    target = project / "figures"
    target.mkdir(parents=True, exist_ok=True)
    for name in FIGURE_NAMES:
        shutil.copy2(FIGURES / name, target / name)


def metadata(
    project: Path,
    title: str,
    subtitle: str,
    document_type: str,
    short_title: str,
) -> Path:
    path = project / "metadata.yaml"
    path.write_text(
        "\n".join(
            [
                f'title: "{title}"',
                f'subtitle: "{subtitle}"',
                f'documenttype: "{document_type}"',
                f'shorttitle: "{short_title}"',
                "author:",
                '  - "Maksymilian Lech"',
                '  - "Borys Kaczmarek"',
                "lang: pl-PL",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def promote_guide_headings(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if line.startswith("### "):
            lines.append(line[1:])
        elif line.startswith("## "):
            lines.append(line[1:])
        else:
            lines.append(line)
    return "\n".join(lines) + "\n"


def sanitize_inline_code(text: str) -> str:
    replacements = {
        "≈": "~=",
        "Δ": "Delta_",
        "μ": "mu",
        "σ": "sigma",
        "λ": "lambda",
        "Σ": "sum",
        "√": "sqrt",
        "ᵀ": "^T",
        "⁻¹": "^(-1)",
        "ŷ": "y_hat",
    }

    def sanitize(match: re.Match[str]) -> str:
        value = match.group(1)
        for source, target in replacements.items():
            value = value.replace(source, target)
        return f"`{value}`"

    return re.sub(r"`([^`\n]+)`", sanitize, text)


def replace_guide_equations(text: str) -> str:
    replacements = {
        "z = (x - średnia) / odchylenie_standardowe": r"z = \frac{x - \mu}{\sigma}",
        "y(k) ≈ C x(k)": r"y(k) \approx Cx(k)",
        "x(k+1) ≈ A x(k) + B u(k)": r"x(k+1) \approx Ax(k) + Bu(k)",
        "x_pred = A x + B u\nP_pred = A P A^T + Q": (
            r"\hat{x}_{k|k-1} = A\hat{x}_{k-1|k-1} + Bu_{k-1}"
            "\n"
            r"P_{k|k-1} = AP_{k-1|k-1}A^T + Q"
        ),
        "e = y - C x_pred": r"e_k = y_k - C\hat{x}_{k|k-1}",
        "K = P_pred C^T (C P_pred C^T + R)^(-1)": (
            r"K_k = P_{k|k-1}C^T(CP_{k|k-1}C^T + R)^{-1}"
        ),
        "x = x_pred + K e": r"\hat{x}_{k|k} = \hat{x}_{k|k-1} + K_ke_k",
        "x(k+1) = A x(k) + B u(k)": r"x(k+1) = Ax(k) + Bu(k)",
        "y_hat(k+1) = C x(k+1) + D u(k)": (
            r"\hat{y}(k+1) = C\hat{x}(k+1) + Du(k)"
        ),
        "y_hat_naive(k+1) = y(k)": r"\hat{y}_{naiwna}(k+1) = y(k)",
        "MAE = (1/n) sum |y_hat - y|": (
            r"MAE = \frac{1}{n}\sum_{i=1}^{n}|\hat{y}_i-y_i|"
        ),
        "RMSE = sqrt((1/n) sum (y_hat - y)^2)": (
            r"RMSE = \sqrt{\frac{1}{n}\sum_{i=1}^{n}(\hat{y}_i-y_i)^2}"
        ),
        "J = sum ||y_pred||^2 + lambda_u sum ||u||^2 + lambda_delta sum ||Delta u||^2": (
            r"J = \sum \|y_{pred}\|^2 + \lambda_u\sum\|u\|^2 "
            r"+ \lambda_{\Delta u}\sum\|\Delta u\|^2"
        ),
    }
    for source, equation in replacements.items():
        text = text.replace(f"```text\n{source}\n```", f"$$\n{equation}\n$$")
    return text


def prepare_guide(project: Path) -> Path:
    text = (DOCS / "PRZEWODNIK_TECHNICZNY.md").read_text(encoding="utf-8")
    text = re.sub(
        r"^# Przewodnik techniczny do projektu\n+"
        r"## Prognozowanie szeregów czasowych i sterowanie MPC dla procesu Tennessee Eastman\n+"
        r"Autorzy projektu:.*?\n"
        r"Przedmiot:.*?\n+",
        "# Jak korzystać z przewodnika\n\n",
        text,
        count=1,
        flags=re.MULTILINE,
    )
    text = text.replace("../artifacts/visualizations/", "figures/")
    text = replace_guide_equations(text)
    text = sanitize_inline_code(text)
    text = promote_guide_headings(text)
    text += (
        "\n# 27. Podstawowe źródła\n\n"
        "1. Downs, J. J., Vogel, E. F., *A plant-wide industrial process control problem*, 1993.\n"
        "2. Kalman, R. E., *A New Approach to Linear Filtering and Prediction Problems*, 1960.\n"
        "3. Qin, S. J., Badgwell, T. A., *A survey of industrial model predictive control technology*, 2003.\n"
        "4. OASIS, *MQTT Version 5.0*, 2019.\n"
        "5. PostgreSQL Global Development Group, *PostgreSQL Documentation*.\n"
        "6. SciPy Developers, *scipy.optimize.lsq_linear documentation*.\n"
    )
    source = project / "content.md"
    source.write_text(text, encoding="utf-8")
    return source


def extract_report_markdown(pandoc: Path, project: Path) -> Path:
    raw_dir = BUILD / "report_extract"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw = BUILD / "report_raw.md"
    run(
        [
            str(pandoc),
            str(DOCS / "Sprawozdanie_TEP_MPC.docx"),
            "--to=markdown",
            "--wrap=none",
            f"--extract-media={raw_dir}",
            f"--output={raw}",
        ]
    )
    text = raw.read_text(encoding="utf-8")
    summary = text.find("# Streszczenie")
    if summary == -1:
        raise RuntimeError("The report summary heading was not found.")
    text = text[summary:]

    for index, name in enumerate(FIGURE_NAMES, start=1):
        image_pattern = re.compile(
            rf"!\[(.*?)\]\([^\n)]*[/\\]media[/\\]image{index}\.png\)"
            rf"(?:\{{[^}}]*\}})?"
        )

        def replace_image(match: re.Match[str], image_name: str = name) -> str:
            caption = re.sub(r"^Rys\.\s*\d+\.\s*", "", match.group(1)).strip()
            return f"![{caption}](figures/{image_name}){{width=96%}}"

        text = image_pattern.sub(replace_image, text)

    equation_lines = [
        ("*z =", r"$$ z = \frac{x-\mu}{\sigma} $$"),
        ("*x(k+1) =", r"$$ x(k+1) = Ax(k) + Bu(k) + w(k) $$"),
        ("*y(k) =", r"$$ y(k) = Cx(k) + Du(k) + v(k) $$"),
        (
            "*x_pred =",
            r"$$ \hat{x}^{-}=A\hat{x}+Bu, \qquad P^{-}=APA^T+Q $$",
        ),
        ("*K =", r"$$ K=P^{-}C^T(CP^{-}C^T+R)^{-1} $$"),
        ("*x = x_pred", r"$$ \hat{x}=\hat{x}^{-}+K(y-C\hat{x}^{-}) $$"),
        (
            "*MAE =",
            r"$$ MAE=\frac{1}{n}\sum_{i=1}^{n}|\hat{y}_i-y_i| $$",
        ),
        (
            "*RMSE =",
            r"$$ RMSE=\sqrt{\frac{1}{n}\sum_{i=1}^{n}(\hat{y}_i-y_i)^2} $$",
        ),
        (
            "*J =",
            r"$$ J=\sum\|y_{pred}\|^2+0{,}2\sum\|u\|^2+0{,}5\sum\|\Delta u\|^2 $$",
        ),
    ]
    output_lines = []
    for line in text.splitlines():
        replacement = next(
            (value for prefix, value in equation_lines if line.startswith(prefix)),
            None,
        )
        output_lines.append(replacement if replacement is not None else line)
    text = "\n".join(output_lines) + "\n"
    text = re.sub(
        r"(?<![<(])(https?://[^\s]+)",
        lambda match: (
            f"<{match.group(1).rstrip('.,;')}>"
            f"{match.group(1)[len(match.group(1).rstrip('.,;')):]}"
        ),
        text,
    )
    text = text.replace(
        "# Bibliografia\n",
        "\\begingroup\n\\small\n\\raggedright\n\n# Bibliografia\n",
        1,
    )
    text += "\n\\endgroup\n"
    text = sanitize_inline_code(text)

    source = project / "content.md"
    source.write_text(text, encoding="utf-8")
    return source


def write_readme(project: Path, document_name: str) -> None:
    (project / "README.txt").write_text(
        "\n".join(
            [
                f"Projekt Overleaf: {document_name}",
                "",
                "Instrukcja:",
                "1. W serwisie Overleaf wybierz New Project -> Upload Project.",
                "2. Wgraj całe archiwum ZIP.",
                "3. Upewnij się, że plikiem głównym jest main.tex.",
                "4. Kompilator ustaw na pdfLaTeX.",
                "",
                "Plik content.md jest źródłem pomocniczym. Overleaf kompiluje main.tex,",
                "więc do zwykłej edycji dokumentu nie jest wymagany Pandoc.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def pandoc_to_latex(pandoc: Path, source: Path, project: Path, metadata_path: Path) -> None:
    run(
        [
            str(pandoc),
            str(source),
            "--standalone",
            "--from=markdown+tex_math_dollars+implicit_figures+pipe_tables",
            "--to=latex",
            "--listings",
            f"--template={TEMPLATE}",
            f"--metadata-file={metadata_path}",
            "--output=main.tex",
        ],
        cwd=project,
    )


def compile_pdf(pdflatex: Path, project: Path) -> None:
    command = [
        str(pdflatex),
        "--enable-installer",
        "-interaction=nonstopmode",
        "-halt-on-error",
        "main.tex",
    ]
    run(command, cwd=project)
    run(command, cwd=project)

    for suffix in ["aux", "log", "out", "toc"]:
        generated = project / f"main.{suffix}"
        if generated.exists():
            generated.unlink()


def zip_project(project: Path, output_name: str) -> Path:
    archive = DOCS / output_name
    if archive.exists():
        archive.unlink()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
        for path in sorted(project.rglob("*")):
            if path.is_file():
                zipped.write(path, path.relative_to(project))
    return archive


def build() -> None:
    pandoc = find_pandoc()
    pdflatex = find_pdflatex()
    reset_directory(BUILD)
    OUTPUT.mkdir(parents=True, exist_ok=True)

    guide = OUTPUT / "Przewodnik_techniczny_TEP"
    reset_directory(guide)
    copy_figures(guide)
    guide_source = prepare_guide(guide)
    guide_metadata = metadata(
        guide,
        "Przewodnik techniczny do projektu",
        "Prognozowanie szeregów czasowych i sterowanie MPC dla procesu Tennessee Eastman",
        "MATERIAŁ DLA OSÓB PREZENTUJĄCYCH",
        "Przewodnik techniczny TEP i MPC",
    )
    pandoc_to_latex(pandoc, guide_source, guide, guide_metadata)
    write_readme(guide, "Przewodnik techniczny TEP i MPC")
    compile_pdf(pdflatex, guide)

    report = OUTPUT / "Sprawozdanie_TEP_MPC"
    reset_directory(report)
    copy_figures(report)
    report_source = extract_report_markdown(pandoc, report)
    report_metadata = metadata(
        report,
        "Prognozowanie i analiza szeregów czasowych",
        "Sterowanie MPC dla procesu Tennessee Eastman",
        "SPRAWOZDANIE PROJEKTOWE",
        "Sprawozdanie TEP i MPC",
    )
    pandoc_to_latex(pandoc, report_source, report, report_metadata)
    write_readme(report, "Sprawozdanie TEP i MPC")
    compile_pdf(pdflatex, report)

    guide_pdf = DOCS / "Przewodnik_techniczny_TEP.pdf"
    report_pdf = DOCS / "Sprawozdanie_TEP_MPC_Overleaf.pdf"
    shutil.copy2(guide / "main.pdf", guide_pdf)
    shutil.copy2(report / "main.pdf", report_pdf)

    guide_zip = zip_project(guide, "Przewodnik_techniczny_TEP_Overleaf.zip")
    report_zip = zip_project(report, "Sprawozdanie_TEP_MPC_Overleaf.zip")

    shutil.rmtree(BUILD)
    print(f"Guide PDF: {guide_pdf}")
    print(f"Guide ZIP: {guide_zip}")
    print(f"Report PDF: {report_pdf}")
    print(f"Report ZIP: {report_zip}")


if __name__ == "__main__":
    build()
