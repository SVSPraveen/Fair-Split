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
from backend.llm_provider import LLMProvider
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


def run_real_timeout_with_real_openrouter_fallback():
    print("=" * 80)
    print(" REAL TIMEOUT + REAL UNMOCKED OPENROUTER FALLBACK PROBE")
    print("=" * 80)

    slow_port = 9877
    server_sock = start_hanging_tcp_server(slow_port)
    slow_url = f"http://127.0.0.1:{slow_port}/v1"

    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if not openrouter_key:
        raise ValueError("OPENROUTER_API_KEY missing from environment!")

    # 1. Instantiate provider: Primary Groq points to slow_url, Fallback points to REAL OpenRouter
    provider = LLMProvider(
        groq_api_key="gsk_fake_key_for_hanging_test",
        openrouter_api_key=openrouter_key
    )

    # Point primary groq client to hanging socket endpoint with max_retries=0 and timeout=10.0
    provider._groq_client = Groq(
        base_url=slow_url,
        api_key="gsk_fake_key_for_hanging_test",
        timeout=10.0,
        max_retries=0
    )

    # Real OpenRouter client
    provider._openrouter_client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=openrouter_key,
        timeout=25.0,
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

    print(f"\n[STEP 1] Calling generate_text_with_status with primary pointed at hanging port {slow_port}...")
    print("Expecting: ~10.0s real socket timeout on primary -> immediate unmocked fallback to OpenRouter API.")

    t_start = time.perf_counter()
    raw_response, used_fb, fb_reason = provider.generate_text_with_status(
        prompt=formatted_prompt,
        timeout_seconds=10.0
    )
    total_elapsed = time.perf_counter() - t_start

    print("\n" + "-" * 80)
    print(f"--> TOTAL REAL WALL-CLOCK TIME: {total_elapsed:.3f} seconds")
    print(f"--> Used Fallback: {used_fb}")
    print(f"--> Fallback Reason: {fb_reason}")
    print("-" * 80)

    print("\n[Raw OpenRouter Response Text]:")
    print(raw_response)

    # Parse into DescriptionData model to verify structural validity
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
    assert 10.0 <= total_elapsed <= 30.0, f"Expected total wall-clock time >= 10.0s, got {total_elapsed:.3f}s"

    print("\n" + "=" * 80)
    print(f" SUCCESS: Primary timed out at ~10s, and real OpenRouter returned valid structured JSON in {total_elapsed:.2f}s total.")
    print("=" * 80)

    server_sock.close()


if __name__ == "__main__":
    run_real_timeout_with_real_openrouter_fallback()
