#!/usr/bin/env python3
"""E2E regression tests for ClawPet using headless Chromium."""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
import time, sys

def make_driver():
    opts = Options()
    opts.binary_location = "/data/data/com.termux/files/usr/bin/headless_shell"
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--headless=new")
    opts.add_argument("--window-size=390,844")
    svc = Service("/data/data/com.termux/files/usr/bin/chromedriver")
    return webdriver.Chrome(service=svc, options=opts)

results = []

def T(name, cond, detail=""):
    s = "PASS" if cond else "FAIL"
    results.append((name, s, detail))
    print(f"  [{s}] {name} {detail}")

def ui(driver):
    return {
        "char": driver.find_element(By.ID, "character").get_attribute("class"),
        "bubble": driver.find_element(By.ID, "bubble").text,
        "send_off": driver.find_element(By.ID, "send-btn").get_attribute("disabled"),
        "stop_on": "show" in driver.find_element(By.ID, "stop-btn").get_attribute("class"),
        "typing_on": "show" in driver.find_element(By.ID, "typing").get_attribute("class"),
        "hf": driver.find_element(By.ID, "auto-listen").is_selected(),
        "tts": driver.find_element(By.ID, "auto-speak").is_selected(),
        "val": driver.find_element(By.ID, "prompt").get_attribute("value"),
        "msgs": len(driver.find_elements(By.CSS_SELECTOR, ".msg")),
        "info": "show" in driver.find_element(By.ID, "info-overlay").get_attribute("class"),
    }

def wait_response(driver, target_msgs, timeout=90):
    for _ in range(timeout // 2):
        time.sleep(2)
        if ui(driver)["msgs"] >= target_msgs:
            return True
    return False

def main():
    driver = make_driver()
    driver.get("http://127.0.0.1:8888")
    time.sleep(3)

    print("=== 1. Initial State ===")
    u = ui(driver)
    T("bubble text", u["bubble"] == "きいてるきゅぴ!", u["bubble"])
    T("send enabled", u["send_off"] is None)
    T("stop hidden", not u["stop_on"])
    T("typing hidden", not u["typing_on"])
    T("hands-free ON", u["hf"])
    T("TTS ON", u["tts"])
    T("info hidden", not u["info"])
    T("no messages", u["msgs"] == 0, str(u["msgs"]))

    print("\n=== 2. Info Modal ===")
    driver.find_element(By.ID, "info-btn").click()
    time.sleep(0.5)
    T("info opens", ui(driver)["info"])
    driver.find_element(By.ID, "info-close").click()
    time.sleep(0.5)
    T("info closes", not ui(driver)["info"])

    print("\n=== 3. Toggle Switches ===")
    driver.find_element(By.ID, "auto-listen").click()
    time.sleep(0.3)
    T("hands-free OFF", not ui(driver)["hf"])
    driver.find_element(By.ID, "auto-listen").click()
    time.sleep(0.3)
    T("hands-free ON", ui(driver)["hf"])
    driver.find_element(By.ID, "auto-speak").click()
    time.sleep(0.3)
    T("TTS OFF", not ui(driver)["tts"])
    # Keep TTS off for clean test (headless has no TTS)

    print("\n=== 4. Empty Send ===")
    driver.find_element(By.ID, "send-btn").click()
    time.sleep(0.3)
    T("no message added", ui(driver)["msgs"] == 0)
    T("still idle", ui(driver)["char"] == "")

    print("\n=== 5. Text Send ===")
    driver.execute_script('document.getElementById("prompt").value="テスト送信"')
    driver.find_element(By.ID, "send-btn").click()
    time.sleep(1)
    u = ui(driver)
    T("thinking state", u["char"] == "thinking", u["char"])
    T("thinking bubble", "かんがえ" in u["bubble"], u["bubble"])
    T("send disabled", u["send_off"] is not None)
    T("typing visible", u["typing_on"])
    T("input cleared", u["val"] == "")
    T("1 user message", u["msgs"] == 1, str(u["msgs"]))
    msg = driver.find_elements(By.CSS_SELECTOR, ".msg")[0]
    T("msg is user", "user" in msg.get_attribute("class"))
    T("msg text", msg.text == "テスト送信", msg.text)

    print("\n=== 6. Response ===")
    wait_response(driver, 2)
    u = ui(driver)
    T("2 messages", u["msgs"] == 2, str(u["msgs"]))
    T("back to idle", u["char"] == "", u["char"])
    T("send re-enabled", u["send_off"] is None)
    T("typing hidden", not u["typing_on"])
    ai = driver.find_elements(By.CSS_SELECTOR, ".msg.ai")
    T("AI message exists", len(ai) == 1)
    T("AI message not empty", len(ai[0].text) > 0 if ai else False)

    print("\n=== 7. No Duplicates ===")
    user_msgs = [m.text for m in driver.find_elements(By.CSS_SELECTOR, ".msg.user")]
    T("single user message", len(user_msgs) == 1, str(len(user_msgs)))

    print("\n=== 8. Second Send ===")
    driver.execute_script('document.getElementById("prompt").value="2回目テスト"')
    driver.find_element(By.ID, "send-btn").click()
    wait_response(driver, 4)
    u = ui(driver)
    T("4 messages", u["msgs"] == 4, str(u["msgs"]))
    user_msgs = [m.text for m in driver.find_elements(By.CSS_SELECTOR, ".msg.user")]
    T("2 user msgs", len(user_msgs) == 2, str(user_msgs))
    T("no duplicates", len(user_msgs) == len(set(user_msgs)), str(user_msgs))

    print("\n=== 9. NEW Button ===")
    driver.find_element(By.ID, "new-btn").click()
    time.sleep(0.5)
    u = ui(driver)
    T("messages cleared", u["msgs"] == 0, str(u["msgs"]))
    T("idle state", u["char"] == "")
    T("bubble reset", u["bubble"] == "きいてるきゅぴ!", u["bubble"])
    stored = driver.execute_script(
        'return JSON.parse(localStorage.getItem("claude-voice-chat") || "[]")'
    )
    T("localStorage cleared", len(stored) == 0)
    T("typing element exists", driver.find_element(By.ID, "typing") is not None)

    print("\n=== 10. Send After NEW ===")
    driver.execute_script('document.getElementById("prompt").value="リセット後"')
    driver.find_element(By.ID, "send-btn").click()
    time.sleep(1)
    T("thinking", ui(driver)["char"] == "thinking")
    wait_response(driver, 2)
    T("response received", ui(driver)["msgs"] == 2, str(ui(driver)["msgs"]))

    print("\n=== 11. Speak/Stop (via JS state simulation) ===")
    # Headless has no TTS audio, so test state transitions via JS
    driver.execute_script("""
        setState("speaking");
        speaking = true;
        currentUtterance = {};
        lastSpokenText = "テスト";
    """)
    time.sleep(0.3)
    u = ui(driver)
    T("speaking state", u["char"] == "speaking", u["char"])
    T("stop visible", u["stop_on"])

    print("\n=== 12. Stop Button ===")
    driver.execute_script("stopSpeaking()")
    time.sleep(0.5)
    u = ui(driver)
    T("idle after stop", u["char"] == "", u["char"])
    T("stop hidden", not u["stop_on"])

    print("\n=== 13. Poop System ===")
    # Clear any auto-spawned poops first
    driver.execute_script(
        "document.querySelectorAll('.poop').forEach(p => {p.remove(); poopCount--})"
    )
    time.sleep(0.5)
    driver.execute_script("spawnPoop()")
    time.sleep(0.5)
    poops = driver.find_elements(By.CSS_SELECTOR, ".poop")
    T("poop spawned", len(poops) == 1, str(len(poops)))
    driver.execute_script("document.querySelector('.poop').click()")
    time.sleep(1)
    remaining = driver.find_elements(By.CSS_SELECTOR, ".poop:not(.clean)")
    T("poop cleaned", len(remaining) == 0, str(len(remaining)))

    print("\n=== 14. Multiple Poops ===")
    driver.execute_script("spawnPoop(); spawnPoop(); spawnPoop()")
    time.sleep(0.5)
    poops = driver.find_elements(By.CSS_SELECTOR, ".poop")
    T("max 3 poops", len(poops) <= 3, str(len(poops)))
    bubble = ui(driver)["bubble"]
    T("cleanup request", "おそうじ" in bubble, bubble)

    # Clean all
    driver.execute_script(
        "document.querySelectorAll('.poop').forEach(p => p.click())"
    )
    time.sleep(1)

    print("\n=== 15. Persistence (localStorage) ===")
    # Messages should be in localStorage
    stored = driver.execute_script(
        'return JSON.parse(localStorage.getItem("claude-voice-chat") || "[]")'
    )
    T("messages persisted", len(stored) > 0, str(len(stored)))

    # Reload and check
    driver.get("http://127.0.0.1:8888")
    time.sleep(3)
    u = ui(driver)
    T("messages survive reload", u["msgs"] > 0, str(u["msgs"]))

    # ==================
    print("\n" + "=" * 50)
    passed = sum(1 for _, s, _ in results if s == "PASS")
    failed = sum(1 for _, s, _ in results if s == "FAIL")
    print(f"TOTAL: {passed} PASS, {failed} FAIL / {len(results)}")
    if failed:
        print("\nFailed:")
        for n, s, d in results:
            if s == "FAIL":
                print(f"  - {n}: {d}")

    driver.quit()
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
