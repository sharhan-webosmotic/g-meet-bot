import asyncio
import os
import subprocess
import time
import datetime
import click
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import undetected_chromedriver as uc

async def run_command_async(command):
    process = await asyncio.create_subprocess_shell(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    return stdout, stderr

async def google_sign_in(email, password, driver):
    # Open Google Sign-In page
    driver.get("https://accounts.google.com")
    time.sleep(2)

    # Enter email
    email_field = driver.find_element(By.NAME, "identifier")
    email_field.send_keys(email)
    driver.save_screenshot("screenshots/email.png")
    time.sleep(1)

    # Click Next
    driver.find_element(By.ID, "identifierNext").click()
    time.sleep(3)

    # Enter password
    password_field = driver.find_element(By.NAME, "Passwd")
    password_field.click()
    password_field.send_keys(password)
    driver.save_screenshot("screenshots/password.png")

    # Submit
    password_field.send_keys(Keys.RETURN)
    time.sleep(5)
    driver.save_screenshot("screenshots/signed_in.png")

async def join_meet():
    # Get environment variables
    meet_url = os.getenv("MEET_URL")
    email = os.getenv("GMAIL_USER_EMAIL")
    password = os.getenv("GMAIL_USER_PASSWORD")
    duration = int(os.getenv("DURATION_IN_MINUTES", "1"))
    max_wait = int(os.getenv("MAX_WAIT_TIME_IN_MINUTES", "2"))

    if not all([meet_url, email, password]):
        print("Error: Please provide MEET_URL, GMAIL_USER_EMAIL, and GMAIL_USER_PASSWORD")
        return

    # Create directories
    for dir_name in ["screenshots", "recordings"]:
        if os.path.exists(dir_name):
            for f in os.listdir(dir_name):
                os.remove(f"{dir_name}/{f}")
        else:
            os.makedirs(dir_name)

    # Initialize Chrome
    print("\nStarting Chrome...")
    options = uc.ChromeOptions()
    options.add_argument("--use-fake-ui-for-media-stream")
    options.add_argument("--window-size=1920x1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-setuid-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-application-cache")
    options.add_argument("--disable-dev-shm-usage")
    log_path = "chromedriver.log"

    driver = uc.Chrome(options=options)
    driver.set_window_size(1920, 1080)

    try:
        # Sign in to Google
        print("\nSigning in to Google...")
        await google_sign_in(email, password, driver)

        # Join meeting
        print(f"\nJoining meeting: {meet_url}")
        
        # Set up browser permissions
        driver.execute_cdp_cmd(
            "Browser.grantPermissions",
            {
                "origin": meet_url,
                "permissions": [
                    "geolocation",
                    "audioCapture",
                    "displayCapture",
                    "videoCapture"
                ],
            },
        )
        
        # Navigate to meet URL and handle initial setup
        driver.get(meet_url)
        time.sleep(5)
        print("\nSaving initial screenshot...")
        driver.save_screenshot("screenshots/initial.png")

        # Turn off microphone and camera
        print("\nTurning off microphone and camera...")
        for _ in range(2):
            try:
                driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.TAB)
                time.sleep(1)
                driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ENTER)
                time.sleep(1)
            except Exception as e:
                print(f"Warning: Could not toggle mic/camera: {str(e)}")
                driver.save_screenshot("screenshots/toggle_error.png")

        # Join
        print("\nLooking for Join button...")
        try:
            # Try multiple possible join button texts
            join_xpaths = [
                '//span[contains(text(), "Join now")]',
                '//span[contains(text(), "Ask to join")]',
                '//span[text()="Join"]'
            ]
            
            join_button = None
            for xpath in join_xpaths:
                try:
                    join_button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, xpath))
                    )
                    print(f"Found join button using: {xpath}")
                    break
                except (TimeoutException, NoSuchElementException):
                    continue
            
            if join_button:
                print("Found Join button, clicking...")
                join_button.click()
                print("Join button clicked successfully")
            else:
                print("Could not find any join button")
                driver.save_screenshot("screenshots/no_join_button.png")
                raise Exception("No join button found")
                
        except Exception as e:
            print(f"Error finding/clicking Join button: {str(e)}")
            driver.save_screenshot("screenshots/join_error.png")
            raise

        print(f"\nIn meeting. Recording for {duration} minutes...")
        
        # Start recording
        print("\nStarting screen recording...")
        record_command = f"ffmpeg -y -video_size 1920x1080 -framerate 30 -f x11grab -i :99 -f pulse -i default -t {duration * 60} -c:v libx264 -pix_fmt yuv420p -c:a aac -strict experimental recordings/output.mp4"
        
        await asyncio.gather(
            run_command_async(record_command)
        )
        
        print("\nRecording completed successfully!")
        print("Recording saved to: recordings/output.mp4")
        
        # Wait for user to exit
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\nExiting...")

    except Exception as e:
        print(f"\nError: {str(e)}")
    finally:
        driver.quit()
        print("\nDone!")

if __name__ == "__main__":
    # Set up audio devices
    try:
        # Clean up any existing PulseAudio files
        subprocess.run("rm -rf /var/run/pulse /var/lib/pulse /root/.config/pulse", shell=True)
        
        # Start PulseAudio daemon
        subprocess.run("pulseaudio -D --verbose --exit-idle-time=-1 --system --disallow-exit", shell=True)
        
        # Set up virtual audio devices
        subprocess.run('pactl load-module module-null-sink sink_name=DummyOutput sink_properties=device.description="Virtual_Dummy_Output"', shell=True)
        subprocess.run('pactl load-module module-null-sink sink_name=MicOutput sink_properties=device.description="Virtual_Microphone_Output"', shell=True)
        subprocess.run("pactl set-default-source MicOutput.monitor", shell=True)
        subprocess.run("pactl set-default-sink MicOutput", shell=True)
    except Exception as e:
        print(f"Warning: Audio setup error: {str(e)}")
    
    # Run the main function
    click.echo("Starting Google Meet recorder...")
    asyncio.run(join_meet())
    click.echo("Finished recording Google Meet.")
