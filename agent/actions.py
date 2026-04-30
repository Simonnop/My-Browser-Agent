import time
from agent.config import PLAYWRIGHT_TIMEOUT_MS

def apply_actions(page, actions: list[dict]):
    error_msg = ""
    successful_actions: list[dict] = []
    
    total_start_time = time.time()
    for action in actions:
        action_start_time = time.time()
        
        action_type = action.get("type", "unknown")
        desc = action_type
        if action_type == "view_screenshot":
            desc = "Requesting screenshot for next cycle"
        elif action_type == "click":
            sel = action.get("selectors", [action.get("selector", "unknown")])[0]
            clicks = action.get("clickCount", action.get("click_count", 1))
            desc = f"Clicking on '{sel}' ({clicks} times)"
        elif action_type == "fill":
            sel = action.get("selectors", [action.get("selector", "unknown")])[0]
            desc = f"Filling text '{action.get('text')}' into '{sel}'"
        elif action_type == "clear":
            sel = action.get("selectors", [action.get("selector", "unknown")])[0]
            desc = f"Clearing text from '{sel}'"
        elif action_type == "select":
            desc = f"Selecting option '{action.get('option')}' from dropdown '{action.get('selector')}'"
        elif action_type == "press":
            desc = f"Pressing key '{action.get('key')}' on '{action.get('selector')}'"
        elif action_type == "scroll":
            desc = f"Scrolling by (x:{action.get('x', 0)}, y:{action.get('y', 800)})"
        elif action_type == "wait":
            desc = f"Waiting for {action.get('ms', PLAYWRIGHT_TIMEOUT_MS)} milliseconds"
        elif action_type == "goto":
            desc = f"Navigating to '{action.get('url')}'"
        elif action_type == "switch_tab":
            desc = f"Switching to tab index {action.get('index', 0)}"
        elif action_type == "exit":
            desc = "Finishing task and exiting program"
            
        print(f"\n▶ Executing action: {desc}")
        print(f"  [Raw JSON] {action}")
        
        try:
            if action_type == "view_screenshot":
                print("  [✓] Action 'view_screenshot' processed.")
            elif action_type == "click":
                selectors = action.get("selectors", [])
                if "selector" in action and not selectors:
                    selectors = [action["selector"]]
                
                clicks = action.get("clickCount", action.get("click_count", 1))
                success = False
                last_err = None
                for sel in selectors:
                    try:
                        loc = page.locator(sel).first
                        try:
                            loc.click(timeout=PLAYWRIGHT_TIMEOUT_MS, click_count=clicks)
                        except Exception:
                            for _ in range(clicks):
                                loc.evaluate("el => el.click()", timeout=PLAYWRIGHT_TIMEOUT_MS)
                        success = True
                        break
                    except Exception as e:
                        last_err = e
                        print(f"  [!] Click failed for selector '{sel}', trying next... Error: {e}")
                        continue
                
                if not success and last_err:
                    raise last_err
            elif action_type == "fill":
                selectors = action.get("selectors", [])
                if "selector" in action and not selectors:
                    selectors = [action["selector"]]
                
                success = False
                last_err = None
                for sel in selectors:
                    try:
                        loc = page.locator(sel).first
                        loc.fill(action.get("text", ""), timeout=PLAYWRIGHT_TIMEOUT_MS)
                        success = True
                        break
                    except Exception as e:
                        last_err = e
                        print(f"  [!] Fill failed for selector '{sel}', trying next... Error: {e}")
                        continue
                
                if not success and last_err:
                    raise last_err
            elif action_type == "clear":
                selectors = action.get("selectors", [])
                if "selector" in action and not selectors:
                    selectors = [action["selector"]]
                
                success = False
                last_err = None
                for sel in selectors:
                    try:
                        loc = page.locator(sel).first
                        loc.click(timeout=PLAYWRIGHT_TIMEOUT_MS)
                        # Fallback for clearing: Control/Meta+A then Backspace
                        import platform
                        modifier = "Meta" if platform.system() == "Darwin" else "Control"
                        loc.press(f"{modifier}+A", timeout=PLAYWRIGHT_TIMEOUT_MS)
                        loc.press("Backspace", timeout=PLAYWRIGHT_TIMEOUT_MS)
                        success = True
                        break
                    except Exception as e:
                        last_err = e
                        print(f"  [!] Clear failed for selector '{sel}', trying next... Error: {e}")
                        continue
                
                if not success and last_err:
                    raise last_err
            elif action_type == "select":
                loc = page.locator(action["selector"]).first
                option_val = action.get("option", "")
                loc.select_option(option_val, timeout=PLAYWRIGHT_TIMEOUT_MS)
            elif action_type == "press":
                loc = page.locator(action["selector"]).first
                loc.press(action.get("key", "Enter"), timeout=PLAYWRIGHT_TIMEOUT_MS)
            elif action_type == "scroll":
                x = int(action.get("x", 0))
                y = int(action.get("y", 800))
                page.mouse.wheel(x, y)
            elif action_type == "wait":
                page.wait_for_timeout(int(action.get("ms", PLAYWRIGHT_TIMEOUT_MS)))
            elif action_type == "goto":
                page.goto(action["url"], wait_until="domcontentloaded")
            elif action_type == "switch_tab":
                index = int(action.get("index", 0))
                if 0 <= index < len(page.context.pages):
                    page = page.context.pages[index]
                else:
                    raise IndexError(f"Tab index out of range: {index}")
            elif action_type == "exit":
                print("  [✓] Task marked as completed. Exiting...")
                import sys
                sys.exit(0)
                    
            action_elapsed = time.time() - action_start_time
            print(f"  [✓] Action completed in {action_elapsed:.2f}s")
            successful_actions.append(action)
        except Exception as e:
            action_elapsed = time.time() - action_start_time
            print(f"  [✗] Action failed in {action_elapsed:.2f}s")
            error_msg = f"Action failed {action}: {type(e).__name__} - {str(e)}"
            break
    
    total_elapsed = time.time() - total_start_time
    if actions:
        print(f"❖ All actions completed / halted in {total_elapsed:.2f}s")
    
    return page, error_msg, successful_actions
