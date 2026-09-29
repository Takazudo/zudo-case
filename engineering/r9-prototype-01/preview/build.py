"""Inline the R9 mesh, artifact table, section images, CSS and Three.js bundle."""
from __future__ import annotations

import base64
import json
from pathlib import Path
import re


PREVIEW = Path(__file__).resolve().parent
R9_ROOT = PREVIEW.parent
REPO_ROOT = R9_ROOT.parents[1]
LIMIT_BYTES = 25 * 1024 * 1024


def _script(source: str) -> str:
    return "<script>\n" + source.replace("</script", "<\\/script") + "\n</script>"


def build() -> Path:
    template = (PREVIEW / "index.html").read_text(encoding="utf-8")
    model = (R9_ROOT / "out" / "preview" / "model-data.js").read_text(encoding="utf-8")
    file_table = json.loads((R9_ROOT / "out" / "preview" / "file-table.json").read_text(encoding="utf-8"))
    section_index = json.loads((R9_ROOT / "out" / "preview" / "sections" / "index.json").read_text(encoding="utf-8"))
    images = {}
    for entry in section_index["sections"]:
        image_path = R9_ROOT / "out" / "preview" / entry["image"]
        if not image_path.is_file():
            raise FileNotFoundError(image_path)
        if image_path.stat().st_size >= LIMIT_BYTES:
            raise ValueError(f"section image exceeds 25 MiB: {image_path}")
        images[entry["image"]] = base64.b64encode(image_path.read_bytes()).decode("ascii")

    replacements = {
        "/*__R9_STYLES__*/": (PREVIEW / "styles.css").read_text(encoding="utf-8"),
        "<!--__R9_THREE__*/": _script((PREVIEW / "three-bundle.js").read_text(encoding="utf-8")),
        "<!--__R9_MODEL_DATA__*/": _script(model),
        "<!--__R9_FILE_TABLE__*/": _script(
            "window.ZUDO_R9_FILE_TABLE = " + json.dumps(file_table, ensure_ascii=False, separators=(",", ":")) + ";"
        ),
        "<!--__R9_SECTION_DATA__*/": _script(
            "window.ZUDO_R9_SECTION_DATA = " + json.dumps(
                {"entries": section_index["sections"], "images": images},
                ensure_ascii=False, separators=(",", ":"),
            ) + ";"
        ),
        "<!--__R9_APP__*/": _script((PREVIEW / "app.js").read_text(encoding="utf-8")),
    }
    for marker, value in replacements.items():
        if template.count(marker) != 1:
            raise ValueError(f"expected one HTML marker, found {template.count(marker)}: {marker}")
        template = template.replace(marker, value)

    license_path = PREVIEW / "THREE-LICENSE.txt"
    license_text = license_path.read_text(encoding="utf-8").replace("--", "- -")
    template = template.replace("<head>", "<head>\n<!--\n" + license_text + "\n-->\n", 1)
    if re.search(r"<(?:script|link)[^>]+(?:src|href)=['\"](?:https?:)?//", template, re.I):
        raise ValueError("external script or stylesheet reference in single-file preview")

    output = REPO_ROOT / "public" / "previews" / "r9-prototype-01.html"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(template, encoding="utf-8", newline="\n")
    if output.stat().st_size >= LIMIT_BYTES:
        raise ValueError(f"single-file preview exceeds 25 MiB: {output}")
    return output


if __name__ == "__main__":
    print(build())
