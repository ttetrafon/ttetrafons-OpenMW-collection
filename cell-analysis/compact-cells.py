import json

cells_by_plugin: dict[str, list[str]] = dict()

with open("all_mods.txt", "r") as all_mods:
  current_plugin: str | None = None
  current_cell: str | None = None

  while line := all_mods.readline():
    l: str = line.strip()
    if (line.startswith('Plugin')):
      # Found next plugin (example line: `Plugin C:\Games\Steam\steamapps\common\Morrowind\Data Files\Morrowind.esm:`)
      last_dash_index: int = line.rindex('\\')

      if (last_dash_index == -1):
        print(f"Something went wrong, could not parse plugin name in line='{line}'")
        continue

      current_plugin = line[last_dash_index + 1 : len(line) - 2]
      current_cell = None

    elif 'cell::' in line.lower():
      # Found a cell
      if current_plugin is None:
        continue

      marker_index: int = line.index("::")
      closing_quote_index: int = line.rindex("\"")

      if marker_index > 0 and closing_quote_index > 0 and closing_quote_index > marker_index:
        current_cell = line[marker_index + 2 : closing_quote_index]
        if current_cell in cells_by_plugin:
          cells_by_plugin[current_cell].append(current_plugin)
        else:
          cells_by_plugin[current_cell] = [current_plugin]

cells_by_plugin = {k: v for k, v in cells_by_plugin.items() if len(v) != 1}
print("Cells modified by multiple plugins:", len(cells_by_plugin))

with open("cells.json", 'w') as data:
  json.dump(cells_by_plugin, data, indent=2)