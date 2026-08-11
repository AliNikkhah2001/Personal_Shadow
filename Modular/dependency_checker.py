import importlib
import importlib.util
import subprocess
import sys


class Colors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"


REQUIRED_PACKAGES = {
    "PyQt6": "PyQt6",
    "PyQt6.QtWebEngineWidgets": "PyQt6-WebEngine",
    "cv2": "opencv-python",
    "requests": "requests",
    "numpy": "numpy",
    "git": "GitPython",
    "machineid": "py-machineid",
    "psutil": "psutil",
    "pymupdf": "PyMuPDF",
}

if sys.platform == "win32":
    REQUIRED_PACKAGES["pyttsx3"] = "pyttsx3"


def is_installed(module_name):
    try:
        if module_name == "PyQt6.QtWebEngineWidgets":
            importlib.import_module(module_name)
            return True
        spec = importlib.util.find_spec(module_name)
        return spec is not None
    except ImportError:
        return False


def install_package(pip_name):
    print(f"[*] Attempting to install {pip_name}...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])
        return True
    except subprocess.CalledProcessError:
        return False


def run_diagnostics():
    print(f"{Colors.HEADER}{Colors.BOLD}===================================================={Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}   MIND PALACE OS - DEPENDENCY DIAGNOSTICS v3.0     {Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}===================================================={Colors.ENDC}\n")

    missing_packages = []

    for import_name, pip_name in REQUIRED_PACKAGES.items():
        if is_installed(import_name):
            print(f"  {Colors.OKGREEN}✓ {import_name} is installed.{Colors.ENDC}")
        else:
            print(f"  {Colors.FAIL}✗ {import_name} is MISSING (requires '{pip_name}').{Colors.ENDC}")
            missing_packages.append(pip_name)

    print("\n" + "=" * 52 + "\n")

    if not missing_packages:
        print(f"{Colors.OKGREEN}{Colors.BOLD}All required libraries are perfectly installed!{Colors.ENDC}")
        print("You can safely run: python main.py")
        sys.exit(0)

    user_input = input("Would you like to automatically install missing packages now? (Y/n): ").strip().lower()

    if user_input in ["", "y", "yes"]:
        for package in missing_packages:
            install_package(package)
        print(f"{Colors.OKGREEN}{Colors.BOLD}Installation complete! Run python main.py{Colors.ENDC}")
    else:
        print(f"\n{Colors.OKBLUE}Installation skipped. Please install manually:{Colors.ENDC}")
        print(f"pip install {' '.join(missing_packages)}")


if __name__ == "__main__":
    run_diagnostics()
