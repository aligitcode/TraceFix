from pathlib import Path

# 1. investigator.py: record whether an answer came from the cache or the API
q = Path("src/tracefix/investigator.py")
s = q.read_text(encoding="utf-8")
old = "    if cache_file.exists():\n        return json.loads(cache_file.read_text(encoding=\"utf-8\"))\n"
new = "    if cache_file.exists():\n        LAST_CALL[\"cached\"] = True\n        return json.loads(cache_file.read_text(encoding=\"utf-8\"))\n    LAST_CALL[\"cached\"] = False\n"
assert old in s
s = s.replace(old, new, 1)
old2 = 'CACHE_DIR = Path("results/cache")\n'
assert old2 in s
s = s.replace(old2, old2 + 'LAST_CALL = {"cached": None}\n', 1)
q.write_text(s, encoding="utf-8")

# 2. evaluate.py: one attempt, stop on quota, count requests
p = Path("evaluate.py")
t = p.read_text(encoding="utf-8")
t = t.replace("from tracefix.investigator import ask_gemini, build_prompt",
              "from tracefix.investigator import LAST_CALL, ask_gemini, build_prompt", 1)
old3 = "            answer = ask_gemini(\n                build_prompt(summary, failing, context, definitions or None)\n            )\n"
new3 = ("            if quota_hit:\n"
        "                row[\"llm_error\"] = \"skipped: daily quota already hit in this run\"\n"
        "                rows.append(row)\n"
        "                continue\n"
        "            answer = ask_gemini(\n"
        "                build_prompt(summary, failing, context, definitions or None),\n"
        "                attempts=1,\n"
        "            )\n"
        "            if LAST_CALL[\"cached\"]:\n"
        "                cache_hits += 1\n"
        "            else:\n"
        "                api_calls += 1\n")
assert old3 in t
t = t.replace(old3, new3, 1)
old4 = "        except Exception as error:\n            row[\"llm_error\"] = str(error)[:200]\n        time.sleep(4)\n"
new4 = ("        except Exception as error:\n"
        "            row[\"llm_error\"] = str(error)[:200]\n"
        "            api_calls += 1\n"
        "            if \"quota\" in str(error).lower():\n"
        "                quota_hit = True\n"
        "        if not LAST_CALL[\"cached\"]:\n"
        "            time.sleep(4)\n")
assert old4 in t
t = t.replace(old4, new4, 1)
old5 = "rows = []\nfor case in cases:\n"
assert old5 in t
t = t.replace(old5, "rows = []\napi_calls = 0\ncache_hits = 0\nquota_hit = False\nfor case in cases:\n", 1)
old6 = "    print(f\"Gemini calls that failed (not scored): {failed}/{total}\")\n"
assert old6 in t
t = t.replace(old6, old6 + "    print(f\"API requests made: {api_calls}   answers from cache: {cache_hits}\")\n", 1)
p.write_text(t, encoding="utf-8")
print("patched")
