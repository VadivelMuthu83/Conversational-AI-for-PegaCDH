"""
install.py — Dependency installer for Copilot Analyst
======================================================
Handles OS/Python-version-specific installation of torch,
then installs everything from requirements.txt.

Usage (from backend/ directory with venv activated):
  python install.py
"""
import platform
import subprocess
import sys


def run(cmd: list, desc: str = "") -> bool:
    label = desc or " ".join(str(x) for x in cmd[3:6])
    print(f"\n  ▶  {label}")
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        print(f"  ✗  Failed (exit {result.returncode})")
        return False
    print(f"  ✓  Done")
    return True


def pip(*args) -> bool:
    return run([sys.executable, "-m", "pip"] + list(args))


def check_import(module: str, name: str) -> bool:
    try:
        __import__(module)
        print(f"  ✓  {name}")
        return True
    except ImportError as e:
        print(f"  ✗  {name}: {e}")
        return False


def main():
    os_name  = platform.system()   # Windows / Darwin / Linux
    py_maj   = sys.version_info.major
    py_min   = sys.version_info.minor
    arch     = platform.machine()  # AMD64 / x86_64 / arm64 / aarch64

    print("=" * 58)
    print("  Copilot Analyst — Dependency Installer")
    print("=" * 58)
    print(f"  OS      : {os_name} {arch}")
    print(f"  Python  : {py_maj}.{py_min}.{sys.version_info.micro}")
    print("=" * 58)

    if py_maj < 3 or (py_maj == 3 and py_min < 10):
        print(f"\n  ERROR: Python 3.10+ required. You have {py_maj}.{py_min}.")
        print("  Download Python 3.12 from https://python.org")
        sys.exit(1)

    # ── 1. Upgrade pip / setuptools / wheel ──────────────────
    print("\n[1/4] Upgrading pip, setuptools, wheel ...")
    pip("install", "--upgrade", "pip", "setuptools", "wheel")

    # ── 2. Install PyTorch CPU ────────────────────────────────
    print("\n[2/4] Installing PyTorch (CPU) ...")

    torch_ok = False
    try:
        import torch
        print(f"  ✓  torch already installed: {torch.__version__}")
        torch_ok = True
    except ImportError:
        pass

    if not torch_ok:
        # Available py313 torch versions from the CPU index:
        # 2.6.0, 2.7.0, 2.7.1, 2.8.0 ... pick latest stable
        torch_ver = "2.7.0"

        if os_name == "Windows" or os_name == "Linux":
            torch_ok = pip(
                "install",
                f"torch=={torch_ver}",
                "--index-url", "https://download.pytorch.org/whl/cpu",
                "--only-binary=:all:",
                "--desc", f"torch {torch_ver} CPU (Windows/Linux)",
            )
        else:
            # macOS — standard PyPI works
            torch_ok = pip(
                "install",
                f"torch=={torch_ver}",
                "--only-binary=:all:",
            )

        if not torch_ok:
            print("  ⚠  Pinned version failed, trying latest torch CPU ...")
            torch_ok = pip(
                "install", "torch",
                "--index-url", "https://download.pytorch.org/whl/cpu",
                "--only-binary=:all:",
            )

    # ── 3. Install requirements.txt ───────────────────────────
    print("\n[3/4] Installing requirements.txt ...")
    ok = pip(
        "install",
        "-r", "requirements.txt",
        "--only-binary=pyarrow,faiss-cpu",
    )
    if not ok:
        print("  ⚠  Retrying without --only-binary ...")
        pip("install", "-r", "requirements.txt")

    # ── 4. Verify imports ─────────────────────────────────────
    print("\n[4/4] Verifying imports ...")

    # (re-import after install)
    import importlib, sys as _sys
    for m in list(_sys.modules.keys()):
        if m.startswith(("fastapi","anthropic","pandas","pyarrow","sentence","faiss","rank_bm25","pypdf","docx","bs4","langsmith","boto3")):
            del _sys.modules[m]

    checks = [
        ("fastapi",               "FastAPI"),
        ("uvicorn",               "Uvicorn"),
        ("pydantic",              "Pydantic"),
        ("pydantic_settings",     "Pydantic Settings"),
        ("pandas",                "Pandas"),
        ("pyarrow",               "PyArrow"),
        ("anthropic",             "Anthropic SDK"),
        ("openai",                "OpenAI SDK"),
        ("sentence_transformers", "SentenceTransformers"),
        ("faiss",                 "FAISS"),
        ("rank_bm25",             "BM25"),
        ("pypdf",                 "PyPDF"),
        ("docx",                  "python-docx"),
        ("bs4",                   "BeautifulSoup4"),
        ("langsmith",             "LangSmith"),
        ("boto3",                 "Boto3 (AWS)"),
    ]

    failed = []
    for module, name in checks:
        if not check_import(module, name):
            failed.append(name)

    print("\n" + "=" * 58)
    if not failed:
        print("  ✅  All dependencies installed successfully!")
    else:
        print(f"  ⚠  {len(failed)} package(s) need attention: {', '.join(failed)}")
        print("     Core app will still work if only optional packages failed.")

    print("""
  Next steps:
    copy ..\\.env .env          (Windows)
    cp ../.env .env              (Mac/Linux)
    uvicorn app.main:app --reload --port 8000
""")
    print("=" * 58)


if __name__ == "__main__":
    main()
