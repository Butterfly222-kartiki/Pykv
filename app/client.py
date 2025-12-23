#!/usr/bin/env python3
"""
PyKV Command-Line Client
A powerful command-line client for interacting with the PyKV store
"""

import asyncio
import aiohttp
import argparse
import json
import time
import sys
from typing import Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor
import threading


class PyKVClient:
    """Asynchronous client for PyKV store"""
    
    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> Dict[str, Any]:
        """Set a key-value pair"""
        data = {"key": key, "value": value}
        if ttl:
            data["ttl"] = ttl
            
        async with self.session.post(f"{self.base_url}/set", json=data) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                error = await resp.text()
                raise Exception(f"SET failed: {resp.status} - {error}")
    
    async def get(self, key: str) -> Optional[str]:
        """Get a value by key"""
        async with self.session.get(f"{self.base_url}/get/{key}") as resp:
            if resp.status == 200:
                result = await resp.json()
                return result.get("value")
            elif resp.status == 404:
                return None
            else:
                error = await resp.text()
                raise Exception(f"GET failed: {resp.status} - {error}")
    
    async def delete(self, key: str) -> bool:
        """Delete a key"""
        async with self.session.delete(f"{self.base_url}/delete/{key}") as resp:
            if resp.status == 200:
                return True
            elif resp.status == 404:
                return False
            else:
                error = await resp.text()
                raise Exception(f"DELETE failed: {resp.status} - {error}")
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get store statistics"""
        async with self.session.get(f"{self.base_url}/stats") as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                error = await resp.text()
                raise Exception(f"STATS failed: {resp.status} - {error}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Check if store is healthy"""
        async with self.session.get(f"{self.base_url}/health") as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                error = await resp.text()
                raise Exception(f"HEALTH failed: {resp.status} - {error}")
    
    async def compact(self) -> Dict[str, Any]:
        """Trigger manual compaction"""
        async with self.session.post(f"{self.base_url}/compact") as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                error = await resp.text()
                raise Exception(f"COMPACT failed: {resp.status} - {error}")


class BenchmarkClient:
    """Multi-threaded client for benchmarking and testing"""
    
    def __init__(self, base_url: str = "http://127.0.0.1:8000", num_threads: int = 10):
        self.base_url = base_url
        self.num_threads = num_threads
        self.results = {
            "operations": 0,
            "errors": 0,
            "total_time": 0,
            "operations_per_second": 0
        }
        self.lock = threading.Lock()
    
    async def _benchmark_worker(self, operations: int, operation_type: str):
        """Worker function for benchmark operations"""
        async with PyKVClient(self.base_url) as client:
            start_time = time.time()
            errors = 0
            
            for i in range(operations):
                try:
                    if operation_type == "set":
                        await client.set(f"bench_key_{i}", f"bench_value_{i}")
                    elif operation_type == "get":
                        await client.get(f"bench_key_{i % 100}")  # Get from existing keys
                    elif operation_type == "mixed":
                        if i % 3 == 0:
                            await client.set(f"bench_key_{i}", f"bench_value_{i}")
                        elif i % 3 == 1:
                            await client.get(f"bench_key_{i % 100}")
                        else:
                            await client.delete(f"bench_key_{i % 200}")
                except Exception as e:
                    errors += 1
                    print(f"Error in operation {i}: {e}")
            
            end_time = time.time()
            duration = end_time - start_time
            
            with self.lock:
                self.results["operations"] += operations
                self.results["errors"] += errors
                self.results["total_time"] = max(self.results["total_time"], duration)
    
    async def run_benchmark(self, total_operations: int, operation_type: str = "mixed"):
        """Run benchmark with multiple concurrent workers"""
        operations_per_thread = total_operations // self.num_threads
        
        print(f"Starting benchmark: {total_operations} {operation_type} operations with {self.num_threads} threads")
        print(f"Operations per thread: {operations_per_thread}")
        
        start_time = time.time()
        
        # Create tasks for concurrent execution
        tasks = []
        for i in range(self.num_threads):
            task = asyncio.create_task(
                self._benchmark_worker(operations_per_thread, operation_type)
            )
            tasks.append(task)
        
        # Wait for all tasks to complete
        await asyncio.gather(*tasks)
        
        end_time = time.time()
        total_duration = end_time - start_time
        
        # Calculate results
        self.results["total_time"] = total_duration
        self.results["operations_per_second"] = self.results["operations"] / total_duration
        
        return self.results


async def interactive_mode(client: PyKVClient):
    """Interactive command-line mode"""
    print("PyKV Interactive Client")
    print("Commands: set <key> <value> [ttl], get <key>, delete <key>, stats, health, compact, quit")
    print("=" * 60)
    
    while True:
        try:
            command = input("pykv> ").strip().split()
            if not command:
                continue
            
            cmd = command[0].lower()
            
            if cmd == "quit" or cmd == "exit":
                break
            elif cmd == "set":
                if len(command) < 3:
                    print("Usage: set <key> <value> [ttl]")
                    continue
                key, value = command[1], command[2]
                ttl = int(command[3]) if len(command) > 3 else None
                result = await client.set(key, value, ttl)
                print(f"[OK] {result}")
            elif cmd == "get":
                if len(command) < 2:
                    print("Usage: get <key>")
                    continue
                key = command[1]
                value = await client.get(key)
                if value is not None:
                    print(f"[OK] {key} = {value}")
                else:
                    print(f"[NOT FOUND] Key '{key}' not found")
            elif cmd == "delete":
                if len(command) < 2:
                    print("Usage: delete <key>")
                    continue
                key = command[1]
                deleted = await client.delete(key)
                if deleted:
                    print(f"[OK] Deleted key '{key}'")
                else:
                    print(f"[NOT FOUND] Key '{key}' not found")
            elif cmd == "stats":
                stats = await client.get_stats()
                print("Store Statistics:")
                for key, value in stats.items():
                    print(f"  {key}: {value}")
            elif cmd == "health":
                health = await client.health_check()
                print(f"Health: {health}")
            elif cmd == "compact":
                result = await client.compact()
                print(f"Compaction: {result}")
            else:
                print(f"Unknown command: {cmd}")
        
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")


async def main():
    """Main CLI function"""
    parser = argparse.ArgumentParser(description="PyKV Command-Line Client")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="PyKV server URL")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    parser.add_argument("--benchmark", "-b", action="store_true", help="Run benchmark")
    parser.add_argument("--operations", "-n", type=int, default=1000, help="Number of operations for benchmark")
    parser.add_argument("--threads", "-t", type=int, default=10, help="Number of threads for benchmark")
    parser.add_argument("--operation-type", choices=["set", "get", "mixed"], default="mixed", help="Benchmark operation type")
    
    # Single operation commands
    parser.add_argument("--set", nargs=2, metavar=("KEY", "VALUE"), help="Set a key-value pair")
    parser.add_argument("--ttl", type=int, help="TTL for set operation")
    parser.add_argument("--get", metavar="KEY", help="Get a value by key")
    parser.add_argument("--delete", metavar="KEY", help="Delete a key")
    parser.add_argument("--stats", action="store_true", help="Get store statistics")
    parser.add_argument("--health", action="store_true", help="Check server health")
    parser.add_argument("--compact", action="store_true", help="Trigger log compaction")
    
    args = parser.parse_args()
    
    try:
        if args.benchmark:
            # Run benchmark
            benchmark = BenchmarkClient(args.url, args.threads)
            results = await benchmark.run_benchmark(args.operations, args.operation_type)
            
            print("\nBenchmark Results:")
            print(f"Total Operations: {results['operations']}")
            print(f"Errors: {results['errors']}")
            print(f"Total Time: {results['total_time']:.2f} seconds")
            print(f"Operations/Second: {results['operations_per_second']:.2f}")
            print(f"Success Rate: {((results['operations'] - results['errors']) / results['operations'] * 100):.1f}%")
            
        elif args.interactive:
            # Interactive mode
            async with PyKVClient(args.url) as client:
                await interactive_mode(client)
        
        else:
            # Single operation mode
            async with PyKVClient(args.url) as client:
                if args.set:
                    key, value = args.set
                    result = await client.set(key, value, args.ttl)
                    print(json.dumps(result, indent=2))
                elif args.get:
                    value = await client.get(args.get)
                    if value is not None:
                        print(value)
                    else:
                        print("Key not found")
                        sys.exit(1)
                elif args.delete:
                    deleted = await client.delete(args.delete)
                    if deleted:
                        print("Key deleted")
                    else:
                        print("Key not found")
                        sys.exit(1)
                elif args.stats:
                    stats = await client.get_stats()
                    print(json.dumps(stats, indent=2, default=str))
                elif args.health:
                    health = await client.health_check()
                    print(json.dumps(health, indent=2))
                elif args.compact:
                    result = await client.compact()
                    print(json.dumps(result, indent=2))
                else:
                    parser.print_help()
    
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())