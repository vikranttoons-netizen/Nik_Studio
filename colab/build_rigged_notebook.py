"""
Build NikStudio_Rigged.ipynb out of the code that is already tested.

    python colab/build_rigged_notebook.py

The notebook used to be a thing you edited by hand, and the two
scripts it needs had to be uploaded to Drive and kept in step with it.
Every time one of them changed, a run went wrong because one of the
three was old. So there is one cell now, it carries the scripts inside
it, and it is generated from the same files the tests run against -
which means it cannot be out of date with them.
"""

import base64
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DRIVER = ROOT / "colab" / "rigged_cell.py"

CARRIED = ("nik_blender.py", "from_mixamo.py")

TARGET = ROOT / "colab" / "NikStudio_Rigged.ipynb"

ABOUT = """\
# Nik Studio - rigged

**One cell. Run it.**

The same `script.txt`, animated by a rig instead of guessed at by a
model - the same character every clip, arms swinging through whole
arcs, and no model deciding what your line meant.

### What Drive needs

```
My Drive / NikStudio / Mixamo /   the character pack, unzipped, whole
My Drive / NikStudio / Moves /    an animation library, if you have one
My Drive / NikStudio / input /    script.txt
```

Nothing else. The scripts this runs are inside the cell - there is no
`.py` file to upload and none to keep in step.

Free CC0 character pack: **quaternius.com**, search *Ultimate Animated
Character*. Free CC0 animation library: **quaternius.itch.io** -
*Universal Animation Library*, name your own price, put 0.

### No GPU needed

Workbench renders flat and fast on a CPU, which is what you want while
finding out whether the movements are right. Switch `ENGINE` to
`"BLENDER_EEVEE_NEXT"` and turn a GPU on when you want it to look like
something.

### Then

Open **NikStudio_Animate.ipynb**, set `SOURCE = "clips"` and
`RUN = "video"`, and it cuts the video from these: beat cut, words on
screen, the song, the preview. One edit, and it does not care what
made the pictures.
"""


def build():

    driver = DRIVER.read_text(encoding="utf-8")

    if "MODULES" not in driver:
        raise SystemExit(f"{DRIVER} does not use MODULES.")

    packed = {
        name: base64.b64encode(
            (ROOT / "blender" / name).read_bytes()).decode("ascii")
        for name in CARRIED
    }

    # Put the scripts in where the driver expects to find them, as one
    # assignment it can read.
    lines = ["MODULES = {"]

    for name, blob in packed.items():

        lines.append(f'    "{name}": (')

        for at in range(0, len(blob), 76):
            lines.append(f'        "{blob[at:at + 76]}"')

        lines.append("    ),")

    lines.append("}")

    carried = "\n".join(lines)

    where = driver.index("import base64")

    cell = driver[:where] + carried + "\n\n" + driver[where:]

    notebook = {
        "cells": [
            {"cell_type": "markdown", "metadata": {},
             "source": ABOUT.splitlines(keepends=True)},
            {"cell_type": "code", "execution_count": None,
             "metadata": {}, "outputs": [],
             "source": cell.splitlines(keepends=True)},
        ],
        "metadata": {
            "colab": {"provenance": []},
            "kernelspec": {"display_name": "Python 3",
                           "name": "python3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 0,
    }

    TARGET.write_text(json.dumps(notebook, indent=1,
                                 ensure_ascii=False) + "\n",
                      encoding="utf-8")

    size = TARGET.stat().st_size

    print(f"{TARGET.relative_to(ROOT)}  ({size // 1024} KB, "
          f"{len(packed)} script(s) carried inside)")

    return TARGET


if __name__ == "__main__":

    build()
