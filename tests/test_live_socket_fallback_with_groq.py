import os
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

from dotenv import load_dotenv
load_dotenv()

from groq import Groq
from openai import OpenAI
from backend.models import DescriptionData
from backend.description_parser import _clean_and_parse_json, PRIMARY_DESCRIPTION_PROMPT_TEMPLATE


def start_hanging_tcp_server(port: int = 9877):
    """Starts a raw TCP socket server that accepts connections and hangs without sending data."""
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(("127.0.0.1", port))
    server_sock.listen(5)

    def handle_connections():
        while True:
            try:
                conn, _ = server_sock.accept()
                try:
                    conn.recv(1024)
                    time.sleep(30) # Hold socket open for 30s
                except Exception:
                    pass
                finally:
                    conn.close()
            except Exception:
                break

    t = threading.Thread(target=handle_connections, daemon=True)
    t.start()
    return server_sock


def run_live_socket_timeout_with_live_fallback():
    print("=" * 80)
    print(" END-TO-END REAL SOCKET TIMEOUT + LIVE UNMOCKED FALLBACK PROBE")
    print("=" * 80)

    slow_port = 9877
    server_sock = start_hanging_tcp_server(slow_port)
    slow_url = f"http://127.0.0.1:{slow_port}/v1"

    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key:
        raise ValueError("GROQ_API_KEY missing from environment!")

    # 1. Primary Client: Points to hanging local socket with native timeout=10.0s, max_retries=0
    primary_client = Groq(
        base_url=slow_url,
        api_key="gsk_dummy_key_for_socket_test",
        timeout=10.0,
        max_retries=0
    )

    # 2. Fallback Client: Real Live Groq API endpoint
    live_fallback_client = Groq(
        api_key=groq_key,
        timeout=15.0,
        max_retries=0
    )

    prompt = (
        "Four of us: Aman, Priya, Karan, Sara. "
        "The Gulab Jamun was shared just by Priya and Karan. "
        "Everything else was common to all four. Priya paid."
    )
    known_items = [
        "Paneer Butter Masala", "Dal Makhani", "Butter Naan",
        "Jeera Rice", "Gulab Jamun", "Masala Papad"
    ]
    formatted_prompt = PRIMARY_DESCRIPTION_PROMPT_TEMPLATE.format(
        known_items_json=json.dumps(known_items),
        description=prompt
    )

    print(f"\n[PHASE 1] Initiating request to primary hanging socket endpoint at {slow_url} (timeout=10.0s)...")
    t_start = time.perf_counter()
    used_fb = False
    fb_reason = None
    raw_response = ""

    # Primary attempt
    try:
        resp = primary_client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{"role": "user", "content": formatted_prompt}],
            timeout=10.0
        )
        raw_response = resp.choices[0].message.content
    except Exception as e:
        t_primary_timeout = time.perf_counter() - t_start
        err_type = type(e).__name__
        print(f"\n--> Primary connection strictly timed out after: {t_primary_timeout:.3f}s")
        print(f"--> Caught Exception Type: {err_type}")
        print(f"--> Primary Failover Reason: 'timeout'")
        used_fb = True
        fb_reason = "timeout"

        print(f"\n[PHASE 2] Executing LIVE UNMOCKED fallback call to real API endpoint...")
        t_fb_start = time.perf_counter()
        fb_resp = live_fallback_client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{"role": "user", "content": formatted_prompt}],
            temperature=0.1,
            max_tokens=2048,
            timeout=15.0
        )
        t_fb_elapsed = time.perf_counter() - t_fb_start
        raw_response = fb_resp.choices[0].message.content or ""
        print(f"--> Live Fallback API Completion Time: {t_fb_elapsed:.3f}s")

    total_elapsed = time.perf_counter() - t_start

    print("\n" + "=" * 80)
    print(" TIMING & FALLBACK AUDIT BREAKDOWN")
    print("=" * 80)
    print(f"Primary Socket Hang Time : {t_primary_timeout:.3f}s  (target: 10.0s)")
    print(f"Live Fallback API Time   : {t_fb_elapsed:.3f}s")
    print(f"TOTAL END-TO-END TIME    : {total_elapsed:.3f}s")
    print(f"Used Fallback Flag       : {used_fb}")
    print(f"Fallback Reason Code     : '{fb_reason}'")
    print("=" * 80)

    print("\n[Live Fallback Raw Response Text]:")
    print(raw_response)

    # Parse into structured DescriptionData model
    parsed_json = _clean_and_parse_json(raw_response)
    desc_obj = DescriptionData.model_validate(parsed_json)
    desc_obj.used_fallback = used_fb
    desc_obj.fallback_reason = fb_reason

    print("\n[Validated Pydantic DescriptionData Output]:")
    print(json.dumps(desc_obj.model_dump(by_alias=True), indent=2))

    assert used_fb is True
    assert fb_reason == "timeout"
    assert len(desc_obj.people) == 4
    assert desc_obj.payer == "Priya"
    assert 9.5 <= t_primary_timeout <= 11.5, f"Primary timeout out of range: {t_primary_timeout:.3f}s"
    assert total_elapsed >= 10.0, f"Total elapsed time too fast: {total_elapsed:.3f}s"

    print("\n" + "=" * 80)
    print(f" TEST PASSED: Real socket timeout held for {t_primary_timeout:.2f}s, then live fallback completed in {t_fb_elapsed:.2f}s (Total: {total_elapsed:.2f}s).")
    print("=" * 80)

    server_sock.close()


if __name__ == "__main__":
    run_live_socket_timeout_with_live_fallback()
