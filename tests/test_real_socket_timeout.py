import sys
import time
import socket
import threading
import json
from pathlib import Path

# Ensure root workspace directory is in python path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Ensure utf-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import groq
from groq import Groq
import openai
from openai import OpenAI
from google import genai
from google.genai import types
import httpx


def start_hanging_tcp_server(port: int = 9876):
    """Starts a raw TCP socket server that accepts connections and hangs without sending data."""
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(("127.0.0.1", port))
    server_sock.listen(5)

    def handle_connections():
        while True:
            try:
                conn, _ = server_sock.accept()
                # Read request but do NOT reply, sleep to force client timeout
                try:
                    conn.recv(1024)
                    time.sleep(35) # Sleep longer than any configured timeout
                except Exception:
                    pass
                finally:
                    conn.close()
            except Exception:
                break

    t = threading.Thread(target=handle_connections, daemon=True)
    t.start()
    return server_sock


def run_real_network_socket_timeout_tests():
    print("=" * 80)
    print(" REAL NETWORK SOCKET WALL-CLOCK TIMEOUT PROBE")
    print(" (Zero mocking of TimeoutError; testing native SDK socket timeout enforcement)")
    print("=" * 80)

    slow_port = 9876
    server_sock = start_hanging_tcp_server(slow_port)
    slow_url = f"http://127.0.0.1:{slow_port}/v1"

    # -------------------------------------------------------------
    # 1. Text Call: Real Groq SDK native 10-second timeout enforcement
    # -------------------------------------------------------------
    print("\n[TEST 1: Groq Text SDK Native Timeout Enforcement]")
    print(f"Connecting to hanging endpoint at {slow_url} with timeout=10.0s...")

    groq_client = Groq(
        base_url=slow_url,
        api_key="gsk_fake_key_for_socket_test",
        timeout=10.0,
        max_retries=0
    )

    t0 = time.perf_counter()
    groq_timeout_caught = False
    groq_error_type = None

    try:
        groq_client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{"role": "user", "content": "Hello"}],
            timeout=10.0
        )
    except Exception as e:
        groq_timeout_caught = True
        groq_error_type = type(e).__name__
        err_msg = str(e)
    t_groq = time.perf_counter() - t0

    print(f"--> Wall-Clock Elapsed Time: {t_groq:.3f} seconds")
    print(f"--> Caught Exception Type: {groq_error_type}")
    print(f"--> Exception Message: {err_msg[:120]}")

    assert groq_timeout_caught is True, "Groq client did not raise timeout exception!"
    assert 9.5 <= t_groq <= 11.5, f"Expected elapsed time close to 10.0s, got {t_groq:.3f}s"
    print(f">>> PASS: Groq client strictly held connection for {t_groq:.3f}s before native SDK timeout fired.")

    # -------------------------------------------------------------
    # 2. Vision Call: Real OpenAI / Vision SDK native 15-second timeout enforcement
    # -------------------------------------------------------------
    print("\n" + "-" * 80)
    print("[TEST 2: Vision SDK Native Timeout Enforcement]")
    print(f"Connecting to hanging endpoint at {slow_url} with timeout=15.0s...")

    vision_client = OpenAI(
        base_url=slow_url,
        api_key="fake_key_for_socket_test",
        timeout=15.0,
        max_retries=0
    )

    t0 = time.perf_counter()
    vision_timeout_caught = False
    vision_error_type = None

    try:
        vision_client.chat.completions.create(
            model="google/gemma-4-26b-a4b-it:free",
            messages=[{"role": "user", "content": "Extract receipt image"}],
            timeout=15.0
        )
    except Exception as e:
        vision_timeout_caught = True
        vision_error_type = type(e).__name__
        err_msg = str(e)
    t_vision = time.perf_counter() - t0

    print(f"--> Wall-Clock Elapsed Time: {t_vision:.3f} seconds")
    print(f"--> Caught Exception Type: {vision_error_type}")
    print(f"--> Exception Message: {err_msg[:120]}")

    assert vision_timeout_caught is True, "Vision client did not raise timeout exception!"
    assert 14.5 <= t_vision <= 16.5, f"Expected elapsed time close to 15.0s, got {t_vision:.3f}s"
    print(f">>> PASS: Vision client strictly held connection for {t_vision:.3f}s before native SDK timeout fired.")

    # -------------------------------------------------------------
    # 3. Gemini Vision Client: Real Google GenAI SDK native timeout test
    # -------------------------------------------------------------
    print("\n" + "-" * 80)
    print("[TEST 3: Google GenAI SDK Native http_options.timeout Enforcement (5.0s test)]")
    gemini_client = genai.Client(
        api_key="fake_key",
        http_options=types.HttpOptions(
            base_url=f"http://127.0.0.1:{slow_port}",
            timeout=5000 # 5000ms
        )
    )

    t0 = time.perf_counter()
    gemini_timeout_caught = False
    gemini_error_type = None
    try:
        gemini_client.models.generate_content(
            model="gemini-3.7-flash",
            contents="Extract receipt",
            config=types.GenerateContentConfig(
                http_options=types.HttpOptions(timeout=5000)
            )
        )
    except Exception as e:
        gemini_timeout_caught = True
        gemini_error_type = type(e).__name__
        err_msg = str(e)
    t_gemini = time.perf_counter() - t0

    print(f"--> Wall-Clock Elapsed Time: {t_gemini:.3f} seconds")
    print(f"--> Caught Exception Type: {gemini_error_type}")
    print(f"--> Exception Message: {err_msg[:120]}")

    assert gemini_timeout_caught is True, "Gemini client did not raise timeout exception!"
    assert 4.5 <= t_gemini <= 6.5, f"Expected elapsed time close to 5.0s, got {t_gemini:.3f}s"
    print(f">>> PASS: Google GenAI client strictly held socket for {t_gemini:.3f}s before native timeout fired.")

    server_sock.close()
    print("\n" + "=" * 80)
    print(" ALL REAL SOCKET TIMEOUT ENFORCEMENT PROBES PASSED")
    print("=" * 80)


if __name__ == "__main__":
    run_real_network_socket_timeout_tests()
