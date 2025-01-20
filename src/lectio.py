# lectio.py

from datetime import datetime
import sys
import time
import traceback
from playwright.sync_api import sync_playwright, expect
from applitools.playwright import Eyes
from .logs import log_event, LogLevel


class LectioBot:
    def __init__(self,
                 school_id,
                 lectio_user,
                 lectio_password,
                 browser_headless=True,
                 applitools_is_active=False,
                 applitools_api_key=None,
                 applitools_app_name=None,
                 applitools_test_name=None):
        self.school_id = school_id
        self.lectio_user = lectio_user
        self.lectio_password = lectio_password
        self.browser_headless = browser_headless
        self.applitools_is_active = applitools_is_active
        self.applitools_api_key = applitools_api_key
        self.applitools_app_name = applitools_app_name
        self.applitools_test_name = applitools_test_name
        self.playwright = None
        self.browser = None
        self.page = None
        self.eyes = None

    def start_playwright(self):
        try:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(headless=self.browser_headless)
            self.page = self.browser.new_page()
            if self.applitools_is_active:
                self.eyes = Eyes()
                self.eyes.api_key = self.applitools_api_key
                self.eyes.open(self.page, self.applitools_app_name, self.applitools_test_name)
        except Exception as e:
            print(f"Error starting Playwright: {e}")
            print(traceback.format_exc())
            sys.exit(1)

    def stop_playwright(self):
        try:
            if self.browser:
                if self.applitools_is_active:
                    self.eyes.close()
                    self.eyes.abort_if_not_closed()
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
        except Exception as e:
            print(f"Error stopping Playwright: {e}")
            print(traceback.format_exc())

    def login_to_lectio(self) -> bool:
        """
        Returns True if login was successful, False otherwise.
        """
        login_url = f"https://www.lectio.dk/lectio/{self.school_id}/login.aspx?prevurl=default.aspx&type=brugernavn"
        print("Accessing webpage: " + login_url)

        try:
            self.page.goto(login_url)
            if self.applitools_is_active:
                self.eyes.check_window("Lectio Login page")

            locator = self.page.locator('.maintitle')
            expect(locator).to_contain_text("Lectio Log ind")
            print("Login page found")
        except Exception as e:
            print("Could not find Lectio login page:")
            print(e)
            return False

        try:
            print("Insert user name")
            self.page.fill("#username", self.lectio_user)

            print("Insert password")
            self.page.fill("#password", self.lectio_password)

            print("Clicking the submit button")
            self.page.click("#m_Content_submitbtn2")

            time.sleep(5)  # sometimes Lectio is slow after login

            # Quick check to confirm we see the username (or something) in the title
            actual_title = self.page.title()
            if self.lectio_user not in actual_title:
                raise AssertionError(f"Expected user '{self.lectio_user}' in title but got '{actual_title}'")

            print("Confirmed that flow has arrived on the main user page")
        except Exception as e:
            print("Error logging in:")
            print(e)
            return False

        return True

    def navigate_to_messages(self) -> bool:
        """
        Navigates to the 'Ny besked' page. Returns True if successful, False otherwise.
        """
        try:
            self.page.goto(f"https://www.lectio.dk/lectio/{self.school_id}/beskeder2.aspx")
            if self.applitools_is_active:
                self.eyes.check_window("Go to 'Lectio Beskeder' page")

            locator = self.page.locator("#s_m_Content_Content_NewMessageLnk")
            expect(locator).to_contain_text("Ny besked")
            self.page.click("#s_m_Content_Content_NewMessageLnk")
            return True
        except Exception as e:
            print("Error navigating to messages:")
            print(e)
            return False

    def send_message(self, send_to: str, subject: str, msg: str, can_be_replied: bool) -> bool:
        """
        Fills out the 'send message' form. Includes a 20x retry for the recipient field.
        Returns True if the send operation was successful, False otherwise.
        """
        locator = self.page.locator("#s_m_Content_Content_MessageThreadCtrl_addRecipientDD_inp")
        try:
            expect(locator, 'end')
        except Exception as e:
            print("Could not load 'Ny besked' page properly.")
            print(e)
            return False

        to_field_locator = self.page.locator("#s_m_Content_Content_MessageThreadCtrl_addRecipientDD_inp")
        MAX_RETRIES = 20
        recipient_clicked = False

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                # Clear the field
                to_field_locator.fill("")
                time.sleep(0.5)

                # Type the recipient's name again
                to_field_locator.type(send_to)
                time.sleep(2)

                # Attempt to click the matching text
                self.page.click(f"text={send_to}")
                recipient_clicked = True
                break
            except Exception as e:
                if attempt == MAX_RETRIES:
                    log_event(
                        timestamp=datetime.now(),
                        level=LogLevel.ERROR,
                        task_id="N/A",
                        receiver=send_to,
                        description=(
                            f"Tried {MAX_RETRIES} times to find/click recipient '{send_to}' but failed. "
                            f"Last error: {str(e)}"
                        )
                    )
                    return False
                else:
                    # Log a small info in each failed attempt (optional)
                    time.sleep(1)

        if not recipient_clicked:
            return False

        # Fill out the subject
        subject_field = self.page.locator("#s_m_Content_Content_MessageThreadCtrl_MessagesGV_ctl02_EditModeHeaderTitleTB_tb")
        subject_field.fill(subject)

        # Check if the message can be replied to
        if not can_be_replied:
            self.page.click("#s_m_Content_Content_MessageThreadCtrl_RepliesNotAllowedChkBox")

        # Fill out the message field
        message_field = self.page.locator(
            "#s_m_Content_Content_MessageThreadCtrl_MessagesGV_ctl02_EditModeContentBBTB_TbxNAME_tb"
        )
        message_field.fill(msg)

        # Send the message
        if self.applitools_is_active:
            self.eyes.check_window("Check if message is filled out correctly")

        try:
            self.page.click("#s_m_Content_Content_MessageThreadCtrl_MessagesGV_ctl02_SendMessageBtn")
            self.page.wait_for_timeout(2000)
        except Exception as e:
            print("Failed to click send button or wait after sending:")
            print(e)
            return False

        # Check if the message was sent
        try:
            locator = self.page.locator("#s_m_Content_Content_MessageThreadCtrl_MessagesGV_ctl02_ctl03_innerBtn")
            expect(locator, 'more_vert')
        except Exception as e:
            print("Didn't find the final indicator that message was sent:")
            print(e)
            return False

        return True

    def send_message_with_full_retry(self, send_to: str, subject: str, task_id: str, msg: str, can_be_replied: bool) -> bool:
        """
        Retries the entire flow (start browser, login, navigate, send) up to 20 times.
        If after 20 attempts it still fails, logs an error and raises an exception.
        """
        MAX_FLOW_RETRIES = 20
        for attempt in range(1, MAX_FLOW_RETRIES + 1):
            try:
                # 1) Start
                self.start_playwright()

                # 2) Login
                if not self.login_to_lectio():
                    raise Exception("login_to_lectio() failed")

                # 3) Navigate to messages
                if not self.navigate_to_messages():
                    raise Exception("navigate_to_messages() failed")

                # 4) Send message
                if not self.send_message(send_to, subject, msg, can_be_replied):
                    raise Exception("send_message() failed")

                # If we got here, success!
                self.stop_playwright()
                return True

            except Exception as e:
                # Must stop the browser before retrying
                self.stop_playwright()

                # If it's the final attempt, log an error + raise
                if attempt == MAX_FLOW_RETRIES:
                    log_event(
                        timestamp=datetime.now(),
                        level=LogLevel.ERROR,
                        task_id=task_id,
                        receiver=send_to,
                        description=(
                            f"Failed entire send flow after {MAX_FLOW_RETRIES} attempts. "
                            f"Last error: {str(e)}"
                        )
                    )
                    raise
                else:
                    # Log a small info or debug
                    log_event(
                        timestamp=datetime.now(),
                        level=LogLevel.INFO,
                        task_id=task_id,
                        receiver=send_to,
                        description=(
                            f"Flow attempt {attempt}/{MAX_FLOW_RETRIES} failed with error: {e}. "
                            "Will retry from scratch..."
                        )
                    )
                    time.sleep(3)  # short cooldown before next attempt

        return False


def main():
    pass


if __name__ == '__main__':
    main()
