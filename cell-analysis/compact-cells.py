import json
import os
import re
from collections import Counter
from typing import Any

# Plugins that are the baseline: we only care about what gets changed on top of them.
BASE_PLUGINS: set[str] = {"morrowind.esm", "tribunal.esm", "bloodmoon.esm"}

INVALID_FILE_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
COORDS_RE = re.compile(r'(-?\d{1,3})x(-?\d{1,3})')
# Reference keys look like `"::villa_stellaris::cellref::70":` where the middle part is the
# lowercase stem of the plugin that originally created the reference.
REF_RE = re.compile(r'^"::(.*)::cellref::(\d+)"\s*:\s*$')


class CellData:
    def __init__(self) -> None:
        self.name: str | None = None
        # plugin -> object_id -> count, for references the plugin itself created
        self.added: dict[str, Counter[str]] = {}
        # plugin -> object_id -> count, for references created elsewhere (base game or another mod)
        self.modified: dict[str, Counter[str]] = {}
        # "origin::ref number" -> object_id, [plugins touching it]; used to find real conflicts
        self.touched: dict[str, tuple[str, list[str]]] = {}

    def plugins(self) -> set[str]:
        return set(self.added) | set(self.modified)


cells: dict[str, CellData] = dict()

with open("all_mods.txt", "r", encoding="utf-8-sig") as all_mods:
    current_plugin: str | None = None
    current_stem: str | None = None
    skip_plugin: bool = False
    current_cell: CellData | None = None
    current_ref_key: str | None = None
    current_origin: str | None = None

    for line in all_mods:
        l: str = line.rstrip()

        if l.startswith('Plugin '):
            # Example: `Plugin C:\Games\Steam\steamapps\common\Morrowind\Data Files\Morrowind.esm:`
            current_plugin = l[l.rindex('\\') + 1:].rstrip(':')
            current_stem = os.path.splitext(current_plugin)[0].lower()
            skip_plugin = current_plugin.lower() in BASE_PLUGINS
            current_cell = None
            current_ref_key = None
            continue

        if current_plugin is None or skip_plugin:
            continue

        if l.startswith('"'):
            # Top level key: a cell (`"Cell::Some Interior":` or `"cell::-2x24":`) or something else
            current_cell = None
            current_ref_key = None
            marker_index: int = l.find("::")
            closing_quote_index: int = l.rindex('"')
            if not l.lower().startswith('"cell::') or closing_quote_index <= marker_index:
                continue

            key: str = l[marker_index + 2: closing_quote_index].strip()
            # Exterior cells like `-2x24` become `-2,24`
            coords = COORDS_RE.fullmatch(key)
            if coords:
                key = f"{coords.group(1)},{coords.group(2)}"

            current_cell = cells.setdefault(key, CellData())
            continue

        if current_cell is None:
            continue

        if l.startswith('  name:'):
            # Exteriors only have a display name inside the data, e.g. `name: "Charach, Villa Stellaris"`
            current_cell.name = l[len('  name:'):].strip().strip('"') or None

        elif l.startswith('    "::'):
            # Start of a reference
            m = REF_RE.match(l.strip())
            if m:
                current_origin = m.group(1)
                current_ref_key = f"{m.group(1)}::{m.group(2)}"
            else:
                current_ref_key = None

        elif l.startswith('      object_id:') and current_ref_key is not None:
            object_id: str = l[len('      object_id:')
                                   :].strip().strip('"').lower()

            if current_origin == current_stem:
                bucket = current_cell.added.setdefault(
                    current_plugin, Counter())
            else:
                bucket = current_cell.modified.setdefault(
                    current_plugin, Counter())
                touched: tuple[str, list[str]] = current_cell.touched.setdefault(
                    current_ref_key, (object_id, list[str]()))
                touched[1].append(current_plugin)

            bucket[object_id] += 1
            current_ref_key = None


# Only cells where at least two non-base plugins make changes are interesting for load order tests
result: dict[str, dict[str, Any]] = {}
for key in sorted(cells):
    cell = cells[key]
    plugins = cell.plugins()
    if len(plugins) < 2:
        continue

    entry: dict[str, Any] = {}
    if cell.name:
        entry["name"] = cell.name

    # Dict order is insertion order, which is the load order in all_mods.txt
    entry["plugins"] = {}
    for plugin in [p for p in list(cell.added) + list(cell.modified) if p in plugins]:
        if plugin in entry["plugins"]:
            continue
        info: dict[str, Any] = {}
        if plugin in cell.added:
            info["added"] = dict(sorted(cell.added[plugin].items()))
        if plugin in cell.modified:
            info["modified"] = dict(sorted(cell.modified[plugin].items()))
        entry["plugins"][plugin] = info

    # References changed by more than one plugin: the actual conflicts, where load order decides
    conflicts: list[dict[str, Any]] = [
        {"ref": ref, "object": obj, "plugins": plugins_}
        for ref, (obj, plugins_) in cell.touched.items()
        if len(set(plugins_)) > 1
    ]
    if conflicts:
        entry["conflicts"] = conflicts

    result[key] = entry

print("Cells modified by multiple plugins:", len(result))
print("... of which with conflicting references:",
      sum(1 for e in result.values() if "conflicts" in e))

OUTPUT_DIR = "cells"
os.makedirs(OUTPUT_DIR, exist_ok=True)
# Remove files from previous runs, so cells that are no longer relevant do not linger
for old in os.listdir(OUTPUT_DIR):
    if old.endswith(".json"):
        os.remove(os.path.join(OUTPUT_DIR, old))

used_names: set[str] = set()
for key, entry in result.items():
    # Cell names can contain characters that are invalid in file names
    base: str = INVALID_FILE_CHARS.sub('_', key).strip(' .')
    file_name: str = base
    n: int = 2
    # Windows file names are case insensitive, so de-duplicate case insensitively
    while file_name.lower() in used_names:
        file_name = f"{base}_{n}"
        n += 1
    used_names.add(file_name.lower())

    # Keep the real cell key inside the file, since the file name may have been altered
    with open(os.path.join(OUTPUT_DIR, file_name + ".jsonc"), 'w', encoding='utf-8') as data:
        json.dump({"cell": key, **entry}, data, indent=2)

print(f"Wrote {len(result)} files to ./{OUTPUT_DIR}/")
