import time
import requests
import json
import statistics

PROXY_URL = "http://localhost:8317/v1/chat/completions"
API_KEY = "sk-pro-rahul"
MODELS = ["gemini-3.5-flash-high", "gemini-3.1-pro-high"]
TEST_PROMPT = 'Translate to English concise: "bhai aaj ka meeting 5 baaje ho sakta hai kya". Output ONLY the translation string.'
NUM_RUNS = 3

def run_benchmark():
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    print("=" * 70)
    print("🚀 LOCAL CLI PROXY MODEL LATENCY BENCHMARK REPORT")
    print(f"Target URL: {PROXY_URL}")
    print(f"Benchmark Runs per Model: {NUM_RUNS}")
    print("=" * 70)

    summary = {}

    for model in MODELS:
        print(f"\n📊 Benchmarking Model: [{model}] ...")
        latencies = []
        token_speeds = []
        outputs = []

        for i in range(1, NUM_RUNS + 1):
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": TEST_PROMPT}]
            }

            start_time = time.perf_counter()
            try:
                response = requests.post(PROXY_URL, headers=headers, json=payload, timeout=30)
                end_time = time.perf_counter()

                elapsed_ms = (end_time - start_time) * 1000
                latencies.append(elapsed_ms)

                if response.status_code == 200:
                    data = response.json()
                    content = data["choices"][0]["message"]["content"].strip()
                    outputs.append(content)
                    
                    usage = data.get("usage", {})
                    completion_tokens = usage.get("completion_tokens", 0)
                    duration_sec = end_time - start_time
                    tokens_per_sec = (completion_tokens / duration_sec) if duration_sec > 0 else 0
                    token_speeds.append(tokens_per_sec)

                    print(f"  Run {i}: Latency = {elapsed_ms:.2f} ms | Output = '{content}'")
                else:
                    print(f"  Run {i}: Error {response.status_code} - {response.text}")
            except Exception as e:
                print(f"  Run {i}: Exception - {e}")

        if latencies:
            summary[model] = {
                "avg_latency": statistics.mean(latencies),
                "min_latency": min(latencies),
                "max_latency": max(latencies),
                "sample_output": outputs[0] if outputs else "N/A"
            }

    print("\n" + "=" * 70)
    print("🏆 FINAL BENCHMARK SUMMARY & COMPARISON")
    print("=" * 70)
    for model, stats in summary.items():
        print(f"Model: {model}")
        print(f"  - Avg Latency : {stats['avg_latency']:.2f} ms")
        print(f"  - Min Latency : {stats['min_latency']:.2f} ms")
        print(f"  - Max Latency : {stats['max_latency']:.2f} ms")
        print(f"  - Sample Output: {stats['sample_output']}")
        print("-" * 50)

if __name__ == "__main__":
    run_benchmark()
