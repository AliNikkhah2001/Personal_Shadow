import sys
import subprocess
import importlib.util

# ANSI color codes for terminal aesthetics
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

# Dictionary mapping the Python import name to the actual pip install name
REQUIRED_PACKAGES = {
    "PyQt6": "PyQt6",
    "PyQt6.QtWebEngineWidgets": "PyQt6-WebEngine", # Crucial: WebEngine is a separate pip package
    "cv2": "opencv-python",
    "requests": "requests",
    "numpy": "numpy",
    "matplotlib": "matplotlib",
    "markdown": "markdown"
}

def is_installed(module_name):
    """Check if a module is installed without actually loading it into memory."""
    try:
        # PyQt6 submodules need to be handled slightly differently
        if module_name == "PyQt6.QtWebEngineWidgets":
            import PyQt6.QtWebEngineWidgets
            return True
            
        spec = importlib.util.find_spec(module_name)
        return spec is not None
    except ImportError:
        return False

def install_package(pip_name):
    """Install a package using the current python executable's pip."""
    print(f"{Colors.OKCYAN}[*] Attempting to install {pip_name}...{Colors.ENDC}")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])
        print(f"  {Colors.OKGREEN}✓ Successfully installed {pip_name}{Colors.ENDC}")
        return True
    except subprocess.CalledProcessError:
        print(f"  {Colors.FAIL}✗ Failed to install {pip_name}. You may need to run this script as Administrator/Root.{Colors.ENDC}")
        return False

def run_diagnostics():
    print(f"{Colors.HEADER}{Colors.BOLD}===================================================={Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}   MIND PALACE OS - DEPENDENCY DIAGNOSTICS v1.0     {Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}===================================================={Colors.ENDC}\n")

    print(f"Using Python executable: {sys.executable}")
    print(f"Python version: {sys.version.split(' ')[0]}\n")

    missing_packages = []
    
    print(f"{Colors.BOLD}Checking Dependencies:{Colors.ENDC}")
    for import_name, pip_name in REQUIRED_PACKAGES.items():
        if is_installed(import_name):
            print(f"  {Colors.OKGREEN}✓ {import_name} is installed.{Colors.ENDC}")
        else:
            print(f"  {Colors.WARNING}✗ {import_name} is MISSING (requires '{pip_name}').{Colors.ENDC}")
            missing_packages.append(pip_name)

    print("\n" + "="*52 + "\n")

    if not missing_packages:
        print(f"{Colors.OKGREEN}{Colors.BOLD}All required libraries are perfectly installed!{Colors.ENDC}")
        print("You can safely run: python main.py")
        sys.exit(0)

    print(f"{Colors.WARNING}{Colors.BOLD}Found {len(missing_packages)} missing packages.{Colors.ENDC}")
    
    user_input = input("Would you like to automatically install missing packages now? (Y/n): ").strip().lower()
    
    if user_input in ['', 'y', 'yes']:
        print("\nStarting installation process...\n")
        all_successful = True
        for package in missing_packages:
            if not install_package(package):
                all_successful = False
                
        print("\n" + "="*52 + "\n")
        if all_successful:
            print(f"{Colors.OKGREEN}{Colors.BOLD}Installation complete! All dependencies are now resolved.{Colors.ENDC}")
            print("You can safely run: python main.py")
        else:
            print(f"{Colors.FAIL}{Colors.BOLD}Some installations failed. Please review the errors above.{Colors.ENDC}")
            print("You can try installing manually with: pip install -r requirements.txt")
    else:
        print(f"\n{Colors.OKBLUE}Installation skipped. Please install these manually:{Colors.ENDC}")
        print(f"pip install {' '.join(missing_packages)}")

if __name__ == "__main__":
    run_diagnostics()