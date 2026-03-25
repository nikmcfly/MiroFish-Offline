#!/usr/bin/env python3
"""
Backtesting script — runs prediction pipeline on resolved markets
and compares simulated probability vs actual outcome.

Usage: source backend/.venv/bin/activate && python tasks/backtest.py
"""

import requests
import time
import json
import sys

API = "http://localhost:5001/api/prediction"

# Resolved markets for backtesting
# Format: (question, description_hint, outcomes, pre_resolution_prices, actual_outcome, volume, condition_id)
BACKTEST_MARKETS = [
    {
        "title": "Will Trump pardon Joe Exotic 'The Tiger King' in 2025?",
        "description": "This market resolves Yes if Donald Trump issues a presidential pardon to Joseph Maldonado-Passage (aka Joe Exotic) at any point during 2025. Joe Exotic was convicted in 2019 on charges of murder-for-hire and wildlife violations. Trump previously considered a pardon during his first term but did not issue one. Joe Exotic's legal team has renewed pardon efforts since Trump's 2024 election win.",
        "outcomes": ["Yes", "No"],
        "prices": [0.12, 0.88],  # approximate pre-resolution market prices
        "actual": "NO",
        "volume": 100000,
        "condition_id": "backtest_tiger_king",
    },
    {
        "title": "Will Zelenskyy wear a suit before July 2025?",
        "description": "This market resolves Yes if Ukrainian President Volodymyr Zelenskyy is photographed wearing a formal suit (jacket and tie or bow tie) at any official public appearance before July 1, 2025. Since Russia's invasion in February 2022, Zelenskyy has exclusively worn military-style olive green clothing at all public appearances as a wartime symbol. Some analysts suggest he may transition to formal attire if ceasefire negotiations advance significantly.",
        "outcomes": ["Yes", "No"],
        "prices": [0.15, 0.85],
        "actual": "NO",
        "volume": 242000,
        "condition_id": "backtest_zelenskyy_suit",
    },
    {
        "title": "Fed decreases interest rates by 50+ bps after January 2026 meeting?",
        "description": "This market resolves Yes if the Federal Reserve decreases the federal funds rate by 50 basis points or more at its January 2026 FOMC meeting. The Fed has been gradually cutting rates since September 2024. As of late 2025, the federal funds rate stands at 4.25-4.50%. Most economists expect the Fed to hold steady or cut by 25bps at most, given persistent inflation and a strong labor market. A 50+ bps cut would signal economic emergency.",
        "outcomes": ["Yes", "No"],
        "prices": [0.05, 0.95],
        "actual": "NO",
        "volume": 235000,
        "condition_id": "backtest_fed_50bps",
    },
    {
        "title": "Khamenei out as Supreme Leader of Iran by January 31, 2026?",
        "description": "This market resolves Yes if Ayatollah Ali Khamenei is no longer serving as the Supreme Leader of Iran by January 31, 2026. Khamenei has been Supreme Leader since 1989. He is 86 years old and has faced health concerns. There is ongoing succession planning, with his son Mojtaba Khamenei seen as a potential successor. Despite protests and internal pressure, the clerical establishment remains firmly in control. Regime change analysts give low probability to near-term leadership change.",
        "outcomes": ["Yes", "No"],
        "prices": [0.08, 0.92],
        "actual": "NO",
        "volume": 50000,
        "condition_id": "backtest_khamenei",
    },
    {
        "title": "Israel military action against Iraq before November 2024?",
        "description": "This market resolves Yes if Israel conducts a confirmed military strike or operation against targets in Iraq before November 1, 2024. Context: Iran-backed militia groups in Iraq have launched drone and rocket attacks on US forces in the region following the October 7 Hamas attack. Israel has historically struck Iranian assets in Iraq, including alleged weapons depots. Tensions are at a multi-decade high with Israel's expanded operations in Gaza and Lebanon, and Iran's direct missile attack on Israel in April 2024.",
        "outcomes": ["Yes", "No"],
        "prices": [0.35, 0.65],
        "actual": "YES",
        "volume": 28000,
        "condition_id": "backtest_israel_iraq",
    },
]


def run_backtest(market_data):
    """Submit a market for prediction and wait for result."""
    print(f"\n{'='*60}")
    print(f"MARKET: {market_data['title']}")
    print(f"  Actual outcome: {market_data['actual']}")
    print(f"  Pre-resolution YES price: {market_data['prices'][0]:.0%}")
    print(f"{'='*60}")

    # Start prediction run
    resp = requests.post(f"{API}/run", json={"market": market_data})
    if not resp.ok:
        print(f"  ERROR starting run: {resp.text}")
        return None

    data = resp.json()["data"]
    run_id = data["run_id"]
    print(f"  Run started: {run_id}")

    # Poll for completion
    start = time.time()
    timeout = 3600  # 60 minutes max
    last_status = ""

    while time.time() - start < timeout:
        resp = requests.get(f"{API}/run/{run_id}/status")
        if not resp.ok:
            time.sleep(5)
            continue

        status_data = resp.json()["data"]
        status = status_data["status"]
        msg = status_data.get("progress_message", "")

        if status != last_status:
            elapsed = int(time.time() - start)
            print(f"  [{elapsed:>4}s] {status}: {msg}")
            last_status = status

        if status == "completed":
            # Fetch full result
            resp = requests.get(f"{API}/run/{run_id}")
            return resp.json()["data"]

        if status == "failed":
            print(f"  FAILED: {status_data.get('error', 'unknown')}")
            return None

        time.sleep(5)

    print(f"  TIMEOUT after {timeout}s")
    return None


def main():
    print("=" * 60)
    print("POLYMARKET BACKTEST — 5 Resolved Markets")
    print("=" * 60)

    # Verify backend is running
    try:
        r = requests.get("http://localhost:5001/health")
        assert r.json()["status"] == "ok"
    except Exception:
        print("ERROR: Backend not running at localhost:5001")
        sys.exit(1)

    results = []

    for market in BACKTEST_MARKETS:
        result = run_backtest(market)

        if result and result.get("signal"):
            sig = result["signal"]
            sentiment = result.get("sentiment", {})

            # Determine if signal was correct
            actual_yes = market["actual"] == "YES"
            sim_prob = sig["simulated_probability"]
            signal_dir = sig["direction"]

            # Correct if: actual YES and signal BUY_YES, or actual NO and signal BUY_NO
            # HOLD counts as correct if edge is small
            if signal_dir == "BUY_YES" and actual_yes:
                correct = True
            elif signal_dir == "BUY_NO" and not actual_yes:
                correct = True
            elif signal_dir == "HOLD":
                correct = None  # Neutral
            else:
                correct = False

            # Brier score: (forecast - outcome)^2
            actual_prob = 1.0 if actual_yes else 0.0
            brier = (sim_prob - actual_prob) ** 2

            entry = {
                "market": market["title"][:60],
                "actual": market["actual"],
                "market_price": market["prices"][0],
                "sim_prob": sim_prob,
                "signal": signal_dir,
                "edge": sig["edge"],
                "confidence": sig["confidence"],
                "correct": correct,
                "brier": brier,
                "stance_for": sentiment.get("stance_counts", {}).get("for", 0),
                "stance_against": sentiment.get("stance_counts", {}).get("against", 0),
                "stance_neutral": sentiment.get("stance_counts", {}).get("neutral", 0),
            }
            results.append(entry)

            symbol = "✓" if correct else ("—" if correct is None else "✗")
            print(f"\n  RESULT: {symbol} Signal={signal_dir}, SimP={sim_prob:.1%}, "
                  f"Market={market['prices'][0]:.1%}, Edge={sig['edge']:+.1%}, Brier={brier:.4f}")
        else:
            results.append({
                "market": market["title"][:60],
                "actual": market["actual"],
                "signal": "FAILED",
                "correct": None,
                "brier": None,
            })

    # Summary
    print("\n" + "=" * 60)
    print("BACKTEST SUMMARY")
    print("=" * 60)

    valid = [r for r in results if r.get("brier") is not None]
    correct = [r for r in valid if r["correct"] is True]
    wrong = [r for r in valid if r["correct"] is False]
    holds = [r for r in valid if r["correct"] is None]

    print(f"\n  Total runs:     {len(results)}")
    print(f"  Completed:      {len(valid)}")
    print(f"  Correct:        {len(correct)}")
    print(f"  Wrong:          {len(wrong)}")
    print(f"  Hold (neutral): {len(holds)}")

    if valid:
        avg_brier = sum(r["brier"] for r in valid) / len(valid)
        print(f"  Avg Brier:      {avg_brier:.4f}  (lower is better, 0.25 = coin flip)")

        accuracy = len(correct) / max(len(correct) + len(wrong), 1)
        print(f"  Directional:    {accuracy:.0%}  ({len(correct)}/{len(correct)+len(wrong)})")

    print("\n  Per-market:")
    for r in results:
        sym = {"True": "✓", "False": "✗", "None": "—"}.get(str(r.get("correct")), "?")
        sig = r.get("signal", "?")
        brier = f"{r['brier']:.4f}" if r.get("brier") is not None else "N/A"
        print(f"    {sym} {r['market'][:55]:<55} | {r['actual']:>3} | {sig:<8} | Brier={brier}")

    # Save results
    with open("tasks/backtest_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Results saved to tasks/backtest_results.json")


if __name__ == "__main__":
    main()
