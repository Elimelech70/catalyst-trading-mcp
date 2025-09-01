#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: startup_and_troubleshoot.py
Version: 1.0.0
Last Updated: 2025-08-30
Purpose: Systematically start and troubleshoot each MCP service

REVISION HISTORY:
v1.0.0 (2025-08-30) - Initial troubleshooting script
"""

import subprocess
import sys
import time
import asyncio
from pathlib import Path
from datetime import datetime
import json
import signal
import os

# Color codes
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
CYAN = '\033[96m'
RESET = '\033[0m'
BOLD = '\033[1m'

class ServiceTester:
    def __init__(self):
        # Set up logging
        self.log_file = f"catalyst_startup_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        self.log_handle = open(self.log_file, 'w')
        self.log(f"Catalyst Trading MCP - Startup Log")
        self.log(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.log("=" * 70)
        
        self.services = [
            {
                'name': 'orchestration',
                'path': 'services/orchestration/orchestration-service.py',
                'priority': 1,
                'description': 'Workflow Coordinator',
                'required': True
            },
            {
                'name': 'news-scanner',
                'path': 'services/news-scanner/news-scanner-service.py',
                'priority': 2,
                'description': 'News Catalyst Scanner',
                'required': False
            },
            {
                'name': 'security-scanner', 
                'path': 'services/security-scanner/security-scanner-service.py',
                'priority': 2,
                'description': 'Market Scanner',
                'required': False
            },
            {
                'name': 'pattern-detector',
                'path': 'services/pattern-detector/pattern-detector-service.py',
                'priority': 3,
                'description': 'Pattern Recognition',
                'required': False
            },
            {
                'name': 'technical-analyzer',
                'path': 'services/technical-analyzer/technical-analyzer-service.py',
                'priority': 3,
                'description': 'Technical Analysis',
                'required': False
            },
            {
                'name': 'risk-manager',
                'path': 'services/risk-manager/risk-manager-service.py',
                'priority': 2,
                'description': 'Risk Management',
                'required': True
            },
            {
                'name': 'trading-executor',
                'path': 'services/trading-executor/trading-executor-service.py',
                'priority': 2,
                'description': 'Order Execution',
                'required': True
            },
            {
                'name': 'reporting',
                'path': 'services/reporting/reporting-service.py',
                'priority': 4,
                'description': 'Performance Reporting',
                'required': False
            }
        ]
        
        # Check for additional services
        self.check_additional_services()
        
        self.results = {}
        self.processes = {}
    
    def log(self, message, console=True):
        """Write to log file and optionally to console"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_message = f"[{timestamp}] {message}"
        
        # Write to file
        self.log_handle.write(log_message + '\n')
        self.log_handle.flush()
        
        # Write to console if requested
        if console:
            # Strip color codes for file but keep for console
            clean_message = message
            for code in [GREEN, RED, YELLOW, BLUE, CYAN, RESET, BOLD]:
                clean_message = clean_message.replace(code, '')
            
            # Write clean version to file if it had colors
            if clean_message != message:
                self.log_handle.write(f"[{timestamp}] {clean_message}\n")
                self.log_handle.flush()
                print(message)  # Print with colors to console
            else:
                print(log_message)  # Print with timestamp to console
        
    def check_additional_services(self):
        """Check for additional service directories"""
        additional = [
            ('news', 'services/news/news-service.py', 'News Processing (Large)'),
            ('scanner', 'services/scanner/scanner-service.py', 'Scanner (Large)'),
            ('pattern', 'services/pattern/pattern-service.py', 'Pattern Detection (Large)'),
            ('technical', 'services/technical/technical-service.py', 'Technical Analysis (Large)'),
            ('trading', 'services/trading/trading-service.py', 'Trading Engine (Large)'),
            ('database', 'services/database/database-mcp-service.py', 'Database Service')
        ]
        
        for name, path, desc in additional:
            if Path(path).exists():
                self.services.append({
                    'name': name,
                    'path': path,
                    'priority': 5,
                    'description': desc,
                    'required': False,
                    'large': True
                })
    
    def print_header(self):
        """Print header"""
        self.log(f"\n{BLUE}{'='*70}{RESET}")
        self.log(f"{BLUE}{BOLD}🎩 CATALYST TRADING MCP - SYSTEM STARTUP & TROUBLESHOOTING{RESET}")
        self.log(f"{BLUE}{'='*70}{RESET}")
        self.log(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.log(f"Services to test: {len(self.services)}")
        self.log(f"Log file: {self.log_file}")
        self.log("")
    
    def test_service_syntax(self, service):
        """Test if service has valid Python syntax"""
        try:
            result = subprocess.run(
                [sys.executable, '-m', 'py_compile', service['path']],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0, result.stderr
        except Exception as e:
            return False, str(e)
    
    def test_service_imports(self, service):
        """Test if service can import its dependencies"""
        test_script = f"""
import sys
sys.path.insert(0, '.')
try:
    with open('{service['path']}', 'r') as f:
        content = f.read()
    
    # Extract imports
    import re
    imports = re.findall(r'^(?:from|import) .*', content, re.MULTILINE)
    
    # Test each import
    failed = []
    for imp in imports[:20]:  # Test first 20 imports
        if not imp.startswith('#'):
            try:
                exec(imp)
            except ImportError as e:
                failed.append((imp, str(e)))
    
    if failed:
        print("FAILED_IMPORTS:", failed)
    else:
        print("IMPORTS_OK")
        
except Exception as e:
    print("ERROR:", e)
"""
        
        try:
            result = subprocess.run(
                [sys.executable, '-c', test_script],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if "IMPORTS_OK" in result.stdout:
                return True, None
            elif "FAILED_IMPORTS" in result.stdout:
                return False, result.stdout
            else:
                return False, result.stdout + result.stderr
                
        except Exception as e:
            return False, str(e)
    
    def start_service(self, service):
        """Try to start a service"""
        try:
            # Start the service
            process = subprocess.Popen(
                [sys.executable, service['path']],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Give it time to start
            time.sleep(2)
            
            # Check if it's still running
            if process.poll() is None:
                # Service is running
                self.processes[service['name']] = process
                
                # Capture some initial output to log
                try:
                    stdout, stderr = process.communicate(timeout=0.1)
                    if stdout:
                        self.log(f"  Initial output: {stdout[:200]}", console=False)
                except subprocess.TimeoutExpired:
                    pass  # Service is still running, which is good
                
                return True, "Running"
            else:
                # Service crashed
                stdout, stderr = process.communicate(timeout=1)
                error = stderr or stdout
                
                # Log full error to file
                self.log(f"  Full error output for {service['name']}:", console=False)
                self.log(f"  STDOUT: {stdout}", console=False)
                self.log(f"  STDERR: {stderr}", console=False)
                
                # Get first meaningful error line for return
                error_lines = [l for l in error.split('\n') if l.strip() and not l.startswith(' ')]
                return False, error_lines[0] if error_lines else "Service exited immediately"
                
        except Exception as e:
            self.log(f"  Exception starting service: {str(e)}", console=False)
            return False, str(e)
    
    def diagnose_error(self, error_msg):
        """Provide diagnosis and fix for common errors"""
        diagnoses = []
        
        if "ModuleNotFoundError" in error_msg:
            module = re.search(r"No module named '([^']+)'", error_msg)
            if module:
                module_name = module.group(1)
                diagnoses.append({
                    'issue': f"Missing module: {module_name}",
                    'fix': f"pip install {module_name}"
                })
        
        elif "ImportError" in error_msg:
            diagnoses.append({
                'issue': "Import error - possibly wrong import statement",
                'fix': "Check imports match MCP SDK documentation"
            })
        
        elif "ValidationError" in error_msg and "url_parsing" in error_msg:
            diagnoses.append({
                'issue': "Resource URI format error",
                'fix': "Ensure resources use format: @mcp.resource('service://path')"
            })
        
        elif "AttributeError" in error_msg:
            attr = re.search(r"'([^']+)' object has no attribute '([^']+)'", error_msg)
            if attr:
                diagnoses.append({
                    'issue': f"Object '{attr.group(1)}' missing attribute '{attr.group(2)}'",
                    'fix': "Check MCP SDK documentation for correct usage"
                })
        
        elif "TypeError" in error_msg:
            diagnoses.append({
                'issue': "Type error in function call",
                'fix': "Check function signatures match MCP requirements"
            })
        
        else:
            diagnoses.append({
                'issue': "Unknown error",
                'fix': "Check full error output below"
            })
        
        return diagnoses
    
    def test_service(self, service):
        """Complete test of a service"""
        self.log(f"\n{CYAN}Testing: {service['name']}{RESET}")
        self.log(f"  Description: {service['description']}")
        self.log(f"  Path: {service['path']}")
        self.log(f"  Required: {'Yes' if service['required'] else 'No'}")
        
        result = {
            'name': service['name'],
            'description': service['description'],
            'syntax': False,
            'imports': False,
            'starts': False,
            'errors': [],
            'diagnosis': []
        }
        
        # Check if file exists
        if not Path(service['path']).exists():
            self.log(f"  {RED}✗ File not found{RESET}")
            result['errors'].append("File not found")
            self.results[service['name']] = result
            return
        
        # Test syntax
        self.log(f"  Checking syntax...", console=True)
        syntax_ok, syntax_error = self.test_service_syntax(service)
        result['syntax'] = syntax_ok
        
        if syntax_ok:
            self.log(f"  Syntax check: {GREEN}✓ PASSED{RESET}")
        else:
            self.log(f"  Syntax check: {RED}✗ FAILED{RESET}")
            self.log(f"  Error details: {syntax_error[:500]}", console=False)  # Log full error to file only
            result['errors'].append(f"Syntax error: {syntax_error[:100]}")
            self.results[service['name']] = result
            return
        
        # Test imports
        self.log(f"  Checking imports...", console=True)
        imports_ok, import_error = self.test_service_imports(service)
        result['imports'] = imports_ok
        
        if imports_ok:
            self.log(f"  Import check: {GREEN}✓ PASSED{RESET}")
        else:
            self.log(f"  Import check: {YELLOW}⚠ WARNING{RESET}")
            if import_error:
                self.log(f"  Import issues: {import_error[:500]}", console=False)  # Full to file only
                result['errors'].append(f"Import issue: {import_error[:200]}")
        
        # Try to start service
        self.log(f"  Starting service...", console=True)
        starts_ok, start_error = self.start_service(service)
        result['starts'] = starts_ok
        
        if starts_ok:
            self.log(f"  Startup: {GREEN}✓ RUNNING{RESET}")
            # Stop it after test
            if service['name'] in self.processes:
                self.processes[service['name']].terminate()
                time.sleep(0.5)
                self.log(f"  Service stopped after successful test", console=False)
        else:
            self.log(f"  Startup: {RED}✗ FAILED{RESET}")
            self.log(f"  Error: {start_error}", console=False)  # Full error to file
            result['errors'].append(start_error)
            
            # Diagnose the error
            if start_error:
                result['diagnosis'] = self.diagnose_error(start_error)
                
                self.log(f"\n  {YELLOW}Diagnosis:{RESET}")
                for diag in result['diagnosis']:
                    self.log(f"    Issue: {diag['issue']}")
                    self.log(f"    Fix:   {diag['fix']}")
        
        self.results[service['name']] = result
    
    def generate_fix_script(self):
        """Generate a script to fix identified issues"""
        fixes_needed = []
        
        for name, result in self.results.items():
            if not result['starts']:
                for diag in result.get('diagnosis', []):
                    if 'pip install' in diag['fix']:
                        fixes_needed.append(diag['fix'])
        
        if fixes_needed:
            script_content = "#!/bin/bash\n"
            script_content += "# Auto-generated fix script\n\n"
            script_content += "echo 'Installing missing dependencies...'\n"
            
            for fix in set(fixes_needed):
                script_content += f"{fix}\n"
            
            with open('fix_dependencies.sh', 'w') as f:
                f.write(script_content)
            
            self.log(f"\n{YELLOW}Fix script created: fix_dependencies.sh{RESET}")
            self.log("Run: bash fix_dependencies.sh")
    
    def print_summary(self):
        """Print test summary"""
        self.log(f"\n{BLUE}{'='*70}{RESET}")
        self.log(f"{BLUE}{BOLD}📊 TEST SUMMARY{RESET}")
        self.log(f"{BLUE}{'='*70}{RESET}\n")
        
        working = []
        broken = []
        fixable = []
        
        for name, result in self.results.items():
            if result['starts']:
                working.append(name)
            elif result['diagnosis']:
                fixable.append(name)
            else:
                broken.append(name)
        
        # Working services
        if working:
            self.log(f"{GREEN}✅ WORKING SERVICES ({len(working)}):{RESET}")
            for name in working:
                self.log(f"  ✓ {name}: {self.results[name]['description']}")
        
        # Fixable services
        if fixable:
            self.log(f"\n{YELLOW}⚠️ FIXABLE SERVICES ({len(fixable)}):{RESET}")
            for name in fixable:
                self.log(f"  ⚠ {name}: {self.results[name]['description']}")
                for diag in self.results[name]['diagnosis'][:1]:
                    self.log(f"     Fix: {diag['fix']}")
        
        # Broken services
        if broken:
            self.log(f"\n{RED}❌ NEEDS MANUAL FIX ({len(broken)}):{RESET}")
            for name in broken:
                self.log(f"  ✗ {name}: {self.results[name]['description']}")
                if self.results[name]['errors']:
                    self.log(f"     Error: {self.results[name]['errors'][0][:80]}")
        
        # Overall status
        self.log(f"\n{BLUE}{'='*70}{RESET}")
        total = len(self.results)
        working_pct = (len(working) / total * 100) if total > 0 else 0
        
        if working_pct >= 75:
            status_color = GREEN
            status = "SYSTEM OPERATIONAL"
        elif working_pct >= 50:
            status_color = YELLOW
            status = "PARTIALLY OPERATIONAL"
        else:
            status_color = RED
            status = "NEEDS ATTENTION"
        
        self.log(f"{status_color}{BOLD}Status: {status} ({len(working)}/{total} services running){RESET}")
        
        # Next steps
        self.log(f"\n{CYAN}🚀 NEXT STEPS:{RESET}")
        
        if working:
            self.log(f"\n1. Start working services:")
            self.log(f"   python {Path(self.services[0]['path']).as_posix()}")
        
        if fixable:
            self.log(f"\n2. Fix issues:")
            seen_fixes = set()
            for name in fixable:
                for diag in self.results[name]['diagnosis']:
                    if diag['fix'] not in seen_fixes:
                        self.log(f"   {diag['fix']}")
                        seen_fixes.add(diag['fix'])
        
        self.log(f"\n3. For manual debugging:")
        self.log(f"   python -m pdb [service-file]")
        self.log(f"   # or")
        self.log(f"   python [service-file] 2>&1 | head -20")
    
    def run_tests(self):
        """Run all tests"""
        self.print_header()
        
        # Sort by priority
        sorted_services = sorted(self.services, key=lambda x: x['priority'])
        
        # Test each service
        for service in sorted_services:
            self.test_service(service)
        
        # Generate fix script if needed
        self.generate_fix_script()
        
        # Print summary
        self.print_summary()
        
        # Save results to file
        self.save_results()
    
    def save_results(self):
        """Save test results to JSON file"""
        results_file = f"service_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(results_file, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        self.log(f"\n{CYAN}Results saved to: {results_file}{RESET}")
        self.log(f"{CYAN}Full log saved to: {self.log_file}{RESET}")
        
        # Close log file
        self.log("\n" + "="*70)
        self.log("End of log")
        self.log_handle.close()

def main():
    """Main execution"""
    tester = None
    try:
        tester = ServiceTester()
        tester.run_tests()
        
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Testing interrupted by user{RESET}")
        # Kill any running processes
        if tester:
            for name, process in tester.processes.items():
                if process.poll() is None:
                    process.terminate()
                    print(f"Stopped: {name}")
            tester.log_handle.close()
    
    except Exception as e:
        print(f"\n{RED}Error: {e}{RESET}")
        import traceback
        traceback.print_exc()
        if tester and hasattr(tester, 'log_handle'):
            tester.log_handle.close()

if __name__ == "__main__":
    main()
