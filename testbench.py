import os
import sys
import ast
import traceback
import importlib

# Ensure PyQt6 is available for UI instantiation tests
try:
    from PyQt6.QtWidgets import QApplication
except ImportError:
    print("\n[!] CRITICAL: PyQt6 is not installed. Please run 'pip install PyQt6'")
    sys.exit(1)

# ANSI Color Codes for beautiful terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def get_all_python_files(exclude_files=None):
    if exclude_files is None:
        exclude_files = ["testbench.py", "build_project.py"]
    py_files = []
    for root, _, files in os.walk("."):
        for file in files:
            if file.endswith(".py") and file not in exclude_files:
                path = os.path.join(root, file)
                py_files.append(path)
    return py_files

def path_to_module(filepath):
    # Convert ./ui/tabs/dashboard.py -> ui.tabs.dashboard
    clean_path = filepath.replace("./", "").replace(".py", "")
    return clean_path.replace(os.sep, ".")

def run_testbench():
    print(f"{Colors.HEADER}{Colors.BOLD}===================================================={Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}   MIND PALACE OS - COMPREHENSIVE TESTBENCH v1.0    {Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}===================================================={Colors.ENDC}\n")

    files = get_all_python_files()
    errors_found = 0

    print(f"{Colors.OKCYAN}[*] PHASE 1: AST Syntax & Compilation Check...{Colors.ENDC}")
    for file in files:
        try:
            with open(file, 'r', encoding='utf-8') as f:
                source = f.read()
            ast.parse(source)
            print(f"  {Colors.OKGREEN}✓ {file} - Syntax OK{Colors.ENDC}")
        except SyntaxError as e:
            errors_found += 1
            print(f"  {Colors.FAIL}✗ {file} - SYNTAX ERROR:{Colors.ENDC}")
            print(f"      {Colors.WARNING}Line {e.lineno}: {e.msg}{Colors.ENDC}")
            print(f"      {e.text.strip() if e.text else ''}")

    print(f"\n{Colors.OKCYAN}[*] PHASE 2: Strict Module Import & Dependency Resolution...{Colors.ENDC}")
    # We must instantiate QApplication before importing GUI modules to prevent QPixmap/QWidget crashes
    app = QApplication.instance() or QApplication(sys.argv)
    
    modules_to_test = [path_to_module(f) for f in files]
    imported_modules = {}

    for mod_name in modules_to_test:
        try:
            imported_modules[mod_name] = importlib.import_module(mod_name)
            print(f"  {Colors.OKGREEN}✓ {mod_name} - Imports Resolved{Colors.ENDC}")
        except Exception as e:
            errors_found += 1
            print(f"  {Colors.FAIL}✗ {mod_name} - IMPORT ERROR:{Colors.ENDC}")
            print(f"      {Colors.WARNING}{type(e).__name__}: {str(e)}{Colors.ENDC}")
            # Print minimal traceback
            tb = traceback.format_exc().splitlines()
            for line in tb[-3:]:
                print(f"      {line}")

    print(f"\n{Colors.OKCYAN}[*] PHASE 3: Headless GUI Instantiation Stress Test...{Colors.ENDC}")
    
    classes_to_test = [
        ("core.config", "ConfigManager"),
        ("core.database", "DatabaseManager"),
        ("vision.tracker", "VisionTracker"),
        ("ui.overlay", "OverlayWidget"),
        ("ui.dialogs", "QuickAddDialog"),
        ("ui.tabs.dashboard", "DashboardWidget"),
        ("ui.tabs.metrics", "MetricsWidget"),
        ("ui.tabs.productivity", "ProductivityWidget"),
        ("ui.tabs.course_progress", "CourseProgressWidget"),
        ("ui.tabs.life_architecture", "LifeArchitectureWidget"),
        ("ui.tabs.habits", "HabitsWidget"),
        ("ui.tabs.day_summary", "DaySummaryWidget"),
        ("ui.tabs.quiz", "QuizEngineWidget"),
        ("ui.tabs.flashcards", "FlashcardWidget"),
        ("ui.tabs.notes", "MarkdownEditorWidget"),
        ("ui.tabs.settings", "SettingsWidget"),
        ("main", "MindPalaceOS")
    ]

    for mod_name, cls_name in classes_to_test:
        if mod_name not in imported_modules:
            print(f"  {Colors.WARNING}⚠ Skipping {cls_name} (Module failed to import){Colors.ENDC}")
            continue

        module = imported_modules[mod_name]
        if hasattr(module, cls_name):
            try:
                TargetClass = getattr(module, cls_name)
                instance = TargetClass()
                print(f"  {Colors.OKGREEN}✓ {cls_name} - Instantiation OK{Colors.ENDC}")
            except Exception as e:
                errors_found += 1
                print(f"  {Colors.FAIL}✗ {cls_name} - INSTANTIATION CRASH:{Colors.ENDC}")
                print(f"      {Colors.WARNING}{type(e).__name__}: {str(e)}{Colors.ENDC}")
                tb = traceback.format_exc().splitlines()
                for line in tb[-4:]:
                    print(f"      {line}")
        else:
            errors_found += 1
            print(f"  {Colors.FAIL}✗ {cls_name} - Class not found in {mod_name}{Colors.ENDC}")

    print(f"\n{Colors.HEADER}{Colors.BOLD}===================================================={Colors.ENDC}")
    if errors_found == 0:
        print(f"{Colors.OKGREEN}{Colors.BOLD}✅ ALL TESTS PASSED! The architecture is 100% stable.{Colors.ENDC}")
    else:
        print(f"{Colors.FAIL}{Colors.BOLD}❌ TESTBENCH FAILED: Found {errors_found} error(s). Please review logs above.{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}===================================================={Colors.ENDC}")

    sys.exit(1 if errors_found > 0 else 0)

if __name__ == "__main__":
    run_testbench()