powershell -NoProfile -Command "& 'C:\games\steam\steamapps\common\Morrowind\Data Files\delta_plugin.exe' query --all --individual match Cell | Out-File -Encoding utf8 'D:\Projects\game-dev\morrowind\cell-analysis\all_mods.txt'"
python "D:\Projects\game-dev\morrowind\cell-analysis\compact-cells.py"
