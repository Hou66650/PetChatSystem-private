"""Read-only toolchain inventory. A ready preflight is NOT engine qualification."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys


def engine_inventory(root: Path) -> dict:
    root = root.resolve()
    version_file = root / "Engine/Build/Build.version"
    result = {"root": str(root), "present": False, "issues": []}
    try:
        version = json.loads(version_file.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as error:
        result["issues"].append("Build.version missing or invalid: " + type(error).__name__)
        return result
    result["present"] = True
    result["version"] = ".".join(str(version.get(key, "?")) for key in
                                ("MajorVersion", "MinorVersion", "PatchVersion"))
    result["build_id"] = version.get("BuildId") or version.get("Changelist")
    result["branch"] = version.get("BranchName", "")
    result["build_version_sha256"] = hashlib.sha256(version_file.read_bytes()).hexdigest()
    if (version.get("MajorVersion"), version.get("MinorVersion")) != (5, 8):
        result["issues"].append("Candidate is UE 5.8; another series requires deliberate qualification.")
    if version.get("IsPromotedBuild") != 1 or "preview" in result["branch"].lower():
        result["issues"].append("Unpromoted/preview build cannot be the release baseline.")
    for relative in ("Engine/Build/BatchFiles/Build.bat", "Engine/Build/BatchFiles/RunUAT.bat",
                     "Engine/Binaries/Win64/UnrealEditor.exe",
                     "Engine/Binaries/Win64/UnrealEditor-Cmd.exe"):
        if not (root / relative).is_file():
            result["issues"].append("Missing " + relative)
    return result


def discover_engines() -> list[Path]:
    roots = set()
    if os.environ.get("UE_ROOT"):
        roots.add(Path(os.environ["UE_ROOT"]))
    manifest = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / \
        "Epic/UnrealEngineLauncher/LauncherInstalled.dat"
    try:
        for item in json.loads(manifest.read_text(encoding="utf-8")).get("InstallationList", []):
            if item.get("AppName", "").startswith("UE_") and item.get("InstallLocation"):
                roots.add(Path(item["InstallLocation"]))
    except (OSError, ValueError):
        pass
    for parent in (Path(r"C:\Program Files\Epic Games"), Path(r"D:\Epic Games"),
                   Path(r"D:\Unreal"), Path(r"D:\Program Files\Epic Games")):
        if parent.is_dir():
            roots.update(parent.glob("UE_*"))
    if sys.platform == "win32":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Epic Games\Unreal Engine\Builds") as key:
                for i in range(winreg.QueryInfoKey(key)[1]):
                    roots.add(Path(winreg.EnumValue(key, i)[1]))
        except OSError:
            pass
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                r"SOFTWARE\EpicGames\Unreal Engine") as key:
                for i in range(winreg.QueryInfoKey(key)[0]):
                    with winreg.OpenKey(key, winreg.EnumKey(key, i)) as sub:
                        roots.add(Path(winreg.QueryValueEx(sub, "InstalledDirectory")[0]))
        except OSError:
            pass
    return sorted(roots, key=str)


def sdk_inventory(roots: list[Path]) -> list[dict]:
    found = []
    for root in sorted({path.resolve() for path in roots}, key=str):
        for header in root.glob("Include/*/um/Windows.h"):
            version = header.parents[1].name
            if (root / "Lib" / version / "um/x64/kernel32.lib").is_file() and \
               (root / "bin" / version / "x64/rc.exe").is_file():
                found.append({"root": str(root), "version": version})
    return found


def tool_inventory() -> dict:
    issues = []
    installs = []
    vswhere = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / \
        "Microsoft Visual Studio/Installer/vswhere.exe"
    if vswhere.is_file():
        proc = subprocess.run([str(vswhere), "-all", "-products", "*", "-requires",
                               "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
                               "-format", "json", "-utf8"], capture_output=True, timeout=30)
        try:
            installs = json.loads(proc.stdout.decode("utf-8-sig")) if proc.returncode == 0 else []
        except ValueError:
            issues.append("vswhere returned invalid JSON")
    if not installs:
        issues.append("MSVC x64 C++ toolchain not found through vswhere")
    compilers = []
    for install in installs:
        root = Path(install["installationPath"])
        for cl in root.glob("VC/Tools/MSVC/*/bin/Hostx64/x64/cl.exe"):
            compilers.append({"version": cl.parents[3].name, "path": str(cl),
                              "visual_studio_version": install.get("installationVersion")})
    if not compilers:
        issues.append("No installed x64 cl.exe found")
    sdk_roots = [Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Windows Kits/10",
                 Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Windows Kits/10"]
    if sys.platform == "win32":
        import winreg
        # Both registry views can exist but point to different SDK content.
        # Never replace a valid fallback with an incomplete registered root.
        for view in (winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY):
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                    r"SOFTWARE\Microsoft\Windows Kits\Installed Roots",
                                    0, winreg.KEY_READ | view) as key:
                    sdk_roots.append(Path(winreg.QueryValueEx(key, "KitsRoot10")[0]))
            except OSError:
                pass
    sdk_installs = sdk_inventory(sdk_roots)
    sdks = sorted({item["version"] for item in sdk_installs})
    if not sdks:
        issues.append("Windows SDK headers, x64 libraries and rc.exe not found")
    return {"compilers": compilers, "windows_sdks": sdks,
            "windows_sdk_installations": sdk_installs,
            "issues": issues}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine-root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    roots = [args.engine_root] if args.engine_root else discover_engines()
    engines = [engine_inventory(root) for root in roots]
    tools = tool_inventory()
    issues = list(tools["issues"])
    if sys.platform != "win32":
        issues.append("Windows build requires Windows host")
    if not any(engine["present"] for engine in engines):
        issues.append("Unreal Engine not found. Install via Epic or pass --engine-root.")
    usable = [engine for engine in engines if not engine["issues"]]
    if len(usable) != 1:
        issues.append("Exactly one eligible engine must be selected with --engine-root.")
    # UBT performs authoritative compiler/SDK compatibility checks during the build.
    result = {"schema_version": 1, "host": {"system": platform.system(),
               "version": platform.version()}, "engines": engines, "tools": tools,
              "issues": issues, "preflight_ready": not issues,
              "qualification_passed": False,
              "note": "Inventory only; UBT compatibility, compile, Cook and launch are still required."}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"preflight_ready": result["preflight_ready"], "issues": issues,
                      "report": str(args.output)}, ensure_ascii=False, indent=2))
    return 0 if result["preflight_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
