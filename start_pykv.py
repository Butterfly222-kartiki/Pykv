#!/usr/bin/env python3
"""
PyKV Startup Script
Easy startup and management for PyKV server with automatic dependency installation
"""

import subprocess
import sys
import os
import time
import argparse
import signal
import importlib.util
from pathlib import Path

# Try to import requests, install if not available
try:
    import requests
except ImportError:
    print("Installing requests...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests


class PyKVManager:
    """PyKV server management utility with dependency management"""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 8000):
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        self.process = None
    
    def check_package(self, package_name):
        """Check if a package is installed"""
        spec = importlib.util.find_spec(package_name)
        return spec is not None
    
    def install_package(self, package):
        """Install a package using pip"""
        try:
            print(f"Installing {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package], 
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except subprocess.CalledProcessError:
            return False
    
    def install_dependencies(self):
        """Install required dependencies"""
        required_packages = [
            "fastapi",
            "uvicorn[standard]", 
            "pydantic"
        ]
        
        optional_packages = [
            "aiofiles",
            "aiohttp"
        ]
        
        print("Checking dependencies...")
        
        # Install required packages
        missing_required = []
        for package in required_packages:
            package_name = package.split('[')[0]  # Handle uvicorn[standard]
            if not self.check_package(package_name):
                if self.install_package(package):
                    print(f"  Installed {package}")
                else:
                    missing_required.append(package)
        
        if missing_required:
            print(f"Failed to install required packages: {', '.join(missing_required)}")
            print("Please install manually:")
            for package in missing_required:
                print(f"  pip install {package}")
            return False
        
        # Install optional packages (best effort)
        for package in optional_packages:
            if not self.check_package(package):
                if self.install_package(package):
                    print(f"  Installed optional package {package}")
                else:
                    print(f"  Could not install optional package {package}")
        
        print("Dependencies ready!")
        return True
    
    def start_server(self, reload: bool = False, workers: int = 1, install_deps: bool = True):
        """Start the PyKV server"""
        
        # Check if we're in the right directory
        if not os.path.exists("app/main.py"):
            print("Error: Please run this script from the PyKV project directory")
            return False
        
        # Install dependencies if requested
        if install_deps:
            if not self.install_dependencies():
                return False
        
        print(f"Starting PyKV server on {self.host}:{self.port}")
        
        # Prepare command
        cmd = [
            sys.executable, "-m", "uvicorn",
            "app.main:app",
            "--host", self.host,
            "--port", str(self.port)
        ]
        
        if reload:
            cmd.append("--reload")
        
        if workers > 1:
            cmd.extend(["--workers", str(workers)])
        
        try:
            # Start server process
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            print(f"Server starting with PID: {self.process.pid}")
            
            # Wait for server to be ready
            if self.wait_for_server(timeout=30):
                print(f"PyKV server is ready at {self.base_url}")
                print(f"API Documentation: {self.base_url}/docs")
                print(f"Web UI: Open ui/index.html in your browser")
                return True
            else:
                print("Server failed to start within timeout")
                # Print server output for debugging
                if self.process.poll() is not None:
                    output, _ = self.process.communicate()
                    print("Server output:")
                    print(output)
                self.stop_server()
                return False
                
        except Exception as e:
            print(f"Failed to start server: {e}")
            return False
    
    def wait_for_server(self, timeout: int = 30) -> bool:
        """Wait for server to be ready"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                response = requests.get(f"{self.base_url}/health", timeout=1)
                if response.status_code == 200:
                    return True
            except requests.exceptions.RequestException:
                pass
            
            time.sleep(1)
            print(".", end="", flush=True)
        
        print()
        return False
    
    def stop_server(self):
        """Stop the PyKV server"""
        if self.process:
            print(f"Stopping PyKV server (PID: {self.process.pid})")
            self.process.terminate()
            
            try:
                self.process.wait(timeout=10)
                print("Server stopped gracefully")
            except subprocess.TimeoutExpired:
                print("Server didn't stop gracefully, forcing...")
                self.process.kill()
                self.process.wait()
                print("Server stopped forcefully")
            
            self.process = None
    
    def get_server_status(self):
        """Get server status and statistics"""
        try:
            # Health check
            health_response = requests.get(f"{self.base_url}/health", timeout=5)
            if health_response.status_code != 200:
                print("Server is not responding")
                return
            
            health = health_response.json()
            print(f"Server Status: {health['status']}")
            print(f"Store Size: {health['store_size']} keys")
            
            # Get detailed stats
            stats_response = requests.get(f"{self.base_url}/stats", timeout=5)
            if stats_response.status_code == 200:
                stats = stats_response.json()
                print("\nStore Statistics:")
                for key, value in stats.items():
                    print(f"   {key}: {value}")
            
            # Get performance metrics
            perf_response = requests.get(f"{self.base_url}/performance", timeout=5)
            if perf_response.status_code == 200:
                perf = perf_response.json()
                print("\nPerformance Metrics:")
                for key, value in perf.items():
                    if key != "operation_breakdown":
                        print(f"   {key}: {value}")
        
        except requests.exceptions.RequestException as e:
            print(f"Cannot connect to server: {e}")
    
    def run_interactive(self):
        """Run server in interactive mode with monitoring"""
        print("PyKV Server Manager")
        print("=" * 40)
        
        if not self.start_server(reload=True):
            return
        
        print("\n" + "="*60)
        print("PyKV Server Running - Interactive Mode")
        print("="*60)
        print("Commands:")
        print("  status  - Show server status and statistics")
        print("  client  - Launch interactive client")
        print("  test    - Run basic functionality test")
        print("  deps    - Check and install dependencies")
        print("  quit    - Stop server and exit")
        print("="*60)
        
        try:
            while True:
                command = input("\npykv-server> ").strip().lower()
                
                if command == "quit" or command == "exit":
                    break
                elif command == "status":
                    self.get_server_status()
                elif command == "client":
                    print("Launching PyKV client...")
                    subprocess.run([sys.executable, "pykv_client.py", "--interactive"])
                elif command == "test":
                    self.run_basic_test()
                elif command == "deps":
                    self.install_dependencies()
                elif command == "help":
                    print("Available commands: status, client, test, deps, quit")
                elif command == "":
                    continue
                else:
                    print(f"Unknown command: {command}")
        
        except KeyboardInterrupt:
            print("\nShutting down...")
        
        finally:
            self.stop_server()
    
    def run_basic_test(self):
        """Run basic functionality test"""
        print("Running basic functionality test...")
        
        try:
            # Test SET
            response = requests.post(f"{self.base_url}/set", 
                                   json={"key": "test_key", "value": "test_value"})
            if response.status_code == 200:
                print("SET operation successful")
            else:
                print(f"SET operation failed: {response.status_code}")
                return
            
            # Test GET
            response = requests.get(f"{self.base_url}/get/test_key")
            if response.status_code == 200:
                data = response.json()
                if data["value"] == "test_value":
                    print("GET operation successful")
                else:
                    print(f"GET returned wrong value: {data['value']}")
            else:
                print(f"GET operation failed: {response.status_code}")
                return
            
            # Test DELETE
            response = requests.delete(f"{self.base_url}/delete/test_key")
            if response.status_code == 200:
                print("DELETE operation successful")
            else:
                print(f"DELETE operation failed: {response.status_code}")
                return
            
            # Verify deletion
            response = requests.get(f"{self.base_url}/get/test_key")
            if response.status_code == 404:
                print("Key properly deleted")
            else:
                print(f"Key still exists after deletion")
            
            print("All basic tests passed!")
        
        except requests.exceptions.RequestException as e:
            print(f"Test failed: {e}")


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="PyKV Server Manager")
    parser.add_argument("--host", default="127.0.0.1", help="Server host")
    parser.add_argument("--port", type=int, default=8000, help="Server port")
    parser.add_argument("--workers", type=int, default=1, help="Number of worker processes")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    parser.add_argument("--status", action="store_true", help="Check server status")
    parser.add_argument("--no-deps", action="store_true", help="Skip dependency installation")
    parser.add_argument("--install-deps", action="store_true", help="Only install dependencies and exit")
    
    args = parser.parse_args()
    
    manager = PyKVManager(args.host, args.port)
    
    if args.install_deps:
        # Only install dependencies
        success = manager.install_dependencies()
        sys.exit(0 if success else 1)
    elif args.status:
        manager.get_server_status()
    elif args.interactive:
        manager.run_interactive()
    else:
        # Start server and keep running
        install_deps = not args.no_deps
        if manager.start_server(reload=args.reload, workers=args.workers, install_deps=install_deps):
            try:
                print("\nPress Ctrl+C to stop the server")
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nShutting down...")
            finally:
                manager.stop_server()


if __name__ == "__main__":
    main()