#!/usr/bin/env python3
"""Selenium test for Crush Pet"""
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import sys

print("Starting Selenium test...")

# Chrome options for Termux
chrome_options = Options()
chrome_options.add_argument('--headless')  # Headless mode
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')
chrome_options.add_argument('--disable-gpu')
chrome_options.add_argument('--window-size=1280,720')

# Use termux chromium
chrome_options.binary_location = '/data/data/com.termux/files/usr/bin/chromium-browser'

print("Initializing Chrome...")
from selenium.webdriver.chrome.service import Service
service = Service('/data/data/com.termux/files/usr/bin/chromedriver')
driver = webdriver.Chrome(service=service, options=chrome_options)

try:
    print("Opening http://127.0.0.1:8888...")
    driver.get("http://127.0.0.1:8888")
    time.sleep(2)
    
    print(f"Page title: {driver.title}")
    
    # Check for any error messages in console
    print("Checking browser console logs...")
    logs = driver.get_log('browser')
    for log in logs:
        print(f"[CONSOLE] {log['level']}: {log['message']}")
    
    # Find input field and send button
    print("Looking for UI elements...")
    try:
        prompt_input = driver.find_element(By.ID, "prompt")
        send_btn = driver.find_element(By.ID, "send-btn")
        bubble = driver.find_element(By.ID, "bubble")
        print(f"Status text: {bubble.text}")
        
        # Send first message
        print("Sending first message...")
        prompt_input.send_keys("こんにちは")
        send_btn.click()
        time.sleep(5)
        
        # Check response
        chat = driver.find_elements(By.CLASS_NAME, "msg")
        print(f"Messages found: {len(chat)}")
        for i, msg in enumerate(chat):
            print(f"  [{i}] {msg.get_attribute('class')}: {msg.text[:50]}...")
        
        # Check status
        print(f"Status after first: {bubble.text}")
        
        # Wait and send second message
        print("Sending second message...")
        prompt_input = driver.find_element(By.ID, "prompt")
        send_btn = driver.find_element(By.ID, "send-btn")
        prompt_input.clear()
        prompt_input.send_keys("カルピス")
        send_btn.click()
        time.sleep(5)
        
        # Check again
        chat = driver.find_elements(By.CLASS_NAME, "msg")
        print(f"Messages after 2nd: {len(chat)}")
        for i, msg in enumerate(chat):
            print(f"  [{i}] {msg.get_attribute('class')}: {msg.text[:50]}...")
        
        # Get console logs again
        logs = driver.get_log('browser')
        for log in logs:
            print(f"[CONSOLE] {log['level']}: {log['message']}")
            
    except Exception as e:
        print(f"UI error: {e}")
        
    print("Test completed successfully!")
    
except Exception as e:
    print(f"Test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    driver.quit()
    print("Browser closed.")
