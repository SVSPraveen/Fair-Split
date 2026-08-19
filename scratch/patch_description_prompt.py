import sys

content = open('backend/description_parser.py', 'r', encoding='utf-8').read()

new_prompt = (
    'PRIMARY_DESCRIPTION_PROMPT_TEMPLATE = """You are an expert bill-splitting and group dining description parser.\n'
    'Given a dining group description and a list of known receipt item names, parse the text into structured JSON.\n'
    '\n'
    'Known Receipt Items:\n'
    '{known_items_json}\n'
    '\n'
    'Description:\n'
    '\\"\\"\\"{{description}}\\"\\"\\"\n'
    '\n'
    'Required JSON Schema:\n'
    '{{\n'
    '  "people": ["string"],\n'
    '  "payer": "string or null",\n'
    '  "item_assignments": [\n'
    '    {{\n'
    '      "item_name": "string",\n'
    '      "consumed_by": ["string"],\n'
    '      "is_shared": true\n'
    '    }}\n'
    '  ],\n'
    '  "unmatched_mentions": ["string"],\n'
    '  "unclear_references": ["string"],\n'
    '  "parsing_assumptions": ["string"]\n'
    '}}\n'
    '\n'
    'CRITICAL RULES:\n'
    '1. Return ONLY valid JSON wrapped in ```json ... ``` or directly as raw JSON.\n'
    '2. "people": List all distinct individuals identified in the group.\n'
    '3. "payer": Identify who paid. If NOT explicitly stated, set "payer" to null. NEVER invent or guess a payer.\n'
    '4. "item_assignments":\n'
    '   - Map every mentioned item to the closest name in Known Receipt Items.\n'
    '   - PARTIAL SHARING: If a subset of people shared an item (e.g. "Arjun and Meena shared the pizza", "2 of us had the beer"), list ONLY those individuals in consumed_by with is_shared: true. The split amount is divided equally among them automatically.\n'
    '   - BLANKET STATEMENTS: If description says "everything else was common to all" or similar, assign ALL remaining unassigned known items to ALL people.\n'
    '   - FUZZY MATCHING: Map abbreviated/informal mentions to the closest Known Receipt Item (e.g. "tikka" to "Chicken Tikka Starter", "naan" to "Garlic Naan"). Note the mapping in parsing_assumptions.\n'
    '5. "unmatched_mentions": Only add if there is genuinely NO plausible match in Known Receipt Items.\n'
    '6. "unclear_references": Ambiguous phrases that cannot be confidently assigned. Never silently drop them.\n'
    '7. "parsing_assumptions": Document every inference (e.g. "tikka mapped to Chicken Tikka Starter", "2 of us interpreted as Arjun and Meena").\n'
    '"""\n'
)

# Fix the description placeholder — it should use triple-escaped quotes properly
new_prompt = new_prompt.replace(
    '\\"\\"\\"{{description}}\\"\\"\\"',
    '\\"\\"\\"' + '{description}' + '\\"\\"\\"'
)

old_start = content.find('PRIMARY_DESCRIPTION_PROMPT_TEMPLATE')
old_end = content.find('\n\nSTRICT_DESCRIPTION_RETRY_PROMPT_TEMPLATE')

if old_start == -1 or old_end == -1:
    print("ERROR: Could not find prompt boundaries")
    sys.exit(1)

new_content = content[:old_start] + new_prompt + content[old_end:]
open('backend/description_parser.py', 'w', encoding='utf-8').write(new_content)
print(f"Done. New file length: {len(new_content)} chars")

# Verify it parses
import importlib.util, types
spec = importlib.util.spec_from_file_location("dp", "backend/description_parser.py")
mod = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(mod)
    print("Import OK. Prompt length:", len(mod.PRIMARY_DESCRIPTION_PROMPT_TEMPLATE))
except Exception as e:
    print("Import FAILED:", e)
