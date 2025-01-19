import logging
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException

logging.basicConfig(filename="x.log", filemode='w',level=logging.INFO, format='%(name)s - %(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BlackboardScraper:
    def __init__(self):
        self.base_url = "https://aulavirtual.up.edu.pe"
        self.download_dir = Path("pdfs")
        self.download_dir.mkdir(exist_ok=True)
        self.files_downloaded = 0
        
        self.options = webdriver.ChromeOptions()
        self.options.add_experimental_option("prefs", {
            "download.default_directory": str(self.download_dir.absolute()),
            "download.prompt_for_download": False,
            "plugins.always_open_pdf_externally": True,
            "safebrowsing.enabled": True
        })
        self.driver = None

    def cleanup(self):
                if self.driver:
                    try:
                        self.driver.quit()
                    except Exception as e:
                        logger.error(f"Error during cleanup: {e}")
                    finally:
                        self.driver = None
    def wait_for_element(self, by, value, timeout=10, condition=EC.presence_of_element_located):
        try:
            return WebDriverWait(self.driver, timeout).until(condition((by, value)))
        except TimeoutException:
            logger.error(f"Timeout waiting for element: {value}")
            return None

    def wait_for_elements(self, by, value, timeout=10):
        try:
            return WebDriverWait(self.driver, timeout).until(
                EC.presence_of_all_elements_located((by, value))
            )
        except TimeoutException:
            logger.error(f"Timeout waiting for elements: {value}")
            return []

    def login(self, username: str, password: str) -> bool:
        try:
            self.driver = webdriver.Chrome(options=self.options)
            self.driver.maximize_window()
            self.driver.get(self.base_url)

            try:
                agree_button = self.wait_for_element(By.ID, "agree_button", timeout=5)
                if agree_button:
                    agree_button.click()
            except:
                pass

            username_input = self.wait_for_element(By.ID, "user_id")
            password_input = self.wait_for_element(By.ID, "password")
            if not (username_input and password_input):
                return False

            username_input.send_keys(username)
            password_input.send_keys(password)

            login_button = self.driver.find_element(By.ID, "entry-login")
            if not login_button:
                return False
            login_button.click()
            
            # Wait for login completion
            return True

        except Exception as e:
            logger.error(f"Login error: {e}")
            self.cleanup()
            return False

    def _download_pdf(self):
        try:
            iframe = self.wait_for_element(By.TAG_NAME, "iframe")
            if not iframe:
                return False

            self.driver.switch_to.frame(iframe)
            download_button = self.wait_for_element(
                By.XPATH, "//button[@title='Descargar']"
            )
            if not download_button:
                return False

            download_button.click()
            time.sleep(2)
            return True

        except Exception as e:
            logger.error(f"Error in _download_pdf: {e}")
            return False
        finally:
            self.driver.switch_to.default_content()

    def _try_download(self):
        try:
            if self._download_pdf():
                self.files_downloaded += 1
                return True

            pdfs = self.driver.find_elements(
            By.XPATH, '//*[starts-with(@class, "makeStylesattachmentMeta")]'
        )
            
            for pdf in pdfs:
                try:
                    pdf.click()
                    time.sleep(1)
                    if self._download_pdf():
                        self.files_downloaded += 1
                    pdf.click()  # Close preview
                    
                except Exception as e:
                    logger.error(f"Error processing PDF: {e}")
                    continue
            
            return True
        except Exception as e:
            logger.error(f"Error in _try_download: {e}")
            return False


    def _process_content(self, element):
        try:
            # Determine if the element is a folder based on its class or other attributes
            classes = element.get_attribute("id").lower()
            is_folder = "folder" in classes  # Adjust the identifier as needed

            if is_folder:
                logger.info(f"Processing folder: {element.text}")
                element.click()
                time.sleep(1)

                self._process_folder_contents()
                logger.info(f"Processed folder: {element.text}")

                # Navigate back after processing the folder
                self.driver.back()
                time.sleep(1)
            else:
                logger.info(f"Processing file: {element.text}")
                element.click()
                time.sleep(1)
                if self._try_download():
                    logger.info(f"Successfully downloaded file: {element.text}")
                else:
                    logger.warning(f"No downloadable content found for file: {element.text}")
                self.driver.back()
                time.sleep(1)

        except StaleElementReferenceException as e:
            logger.error(f"StaleElementReferenceException in _process_content: {e}")
        except Exception as e:
            logger.error(f"Error processing content: {e}")


    def _process_folder_contents(self):
        try:
            contents = WebDriverWait(self.driver, 10).until(
                EC.presence_of_all_elements_located(
                    (By.XPATH, "//*[starts-with(@class, 'content-list-item')]")
                )
            )
            logger.info(f"Found {len(contents)} items in folder.")

            for index in range(len(contents)):
                try:
                    # Re-locate contents to avoid stale elements
                    updated_contents = self.driver.find_elements(
                        By.XPATH, "//*[starts-with(@class, 'content-list-item')]"
                    )
                    if index >= len(updated_contents):
                        logger.warning("Index out of range while processing contents.")
                        break

                    self._process_content(updated_contents[index])
                except StaleElementReferenceException:
                    logger.warning("Stale element encountered. Retrying...")
                    time.sleep(1)
                    updated_contents = self.driver.find_elements(
                        By.XPATH, "//*[starts-with(@class, 'content-list-item')]"
                    )
                    if index < len(updated_contents):
                        self._process_content(updated_contents[index])
                except Exception as e:
                    logger.error(f"Error processing folder content at index {index}: {e}")
                    continue

        except TimeoutException:
            logger.error("Timeout waiting for folder contents.")
        except Exception as e:
            logger.error(f"Error in _process_folder_contents: {e}")


    def download_course_files(self) -> int:
        try:
            self.driver.get(f"{self.base_url}/ultra/course")
            logger.info("Navigated to courses page.")
            time.sleep(2)

            course_list = self.wait_for_element(By.CLASS_NAME, "course-org-list", timeout=10)
            if not course_list:
                logger.error("Course list not found.")
                return self.files_downloaded

            courses = self.wait_for_elements(By.TAG_NAME, "bb-base-course-card", timeout=10)
            logger.info(f"Found {len(courses)} courses.")

            for i in range(len(courses)):
                try:
                    # Re-locate fresh courses each iteration
                    updated_courses = self.driver.find_elements(By.TAG_NAME, "bb-base-course-card")
                    if i >= len(updated_courses):
                        logger.warning("Course index out of range.")
                        break

                    course = updated_courses[i]
                    course_title = course.text.strip()
                    logger.info(f"Processing course {i+1}: {course_title}")
                    course.click()
                    time.sleep(2)

                    # Process materials within the course
                    materials = self.wait_for_elements(
                        By.XPATH, 
                        '//*[contains(@class, "content-list-item")]',
                        timeout=10
                    )
                    logger.info(f"Found {len(materials)} materials in course '{course_title}'.")

                    for j in range(len(materials)):
                        try:
                            # Re-locate fresh materials each iteration
                            updated_materials = self.driver.find_elements(
                                By.XPATH, "//*[contains(@class, 'content-list-item')]"
                            )
                            if j >= len(updated_materials):
                                logger.warning("Material index out of range.")
                                break

                            material = updated_materials[j]
                            logger.info(f"Processing material {j+1} in course '{course_title}'.")
                            self._process_content(material)
                        except StaleElementReferenceException as e:
                            logger.error(f"StaleElementReferenceException while processing material {j+1}: {e}")
                            continue
                        except Exception as e:
                            logger.error(f"Error processing material {j+1}: {e}")
                            continue

                    # Navigate back to courses list
                    self.driver.back()
                    time.sleep(2)

                except StaleElementReferenceException as e:
                    logger.error(f"StaleElementReferenceException while processing course {i+1}: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Error processing course {i+1}: {e}")
                    continue

            logger.info(f"Total files downloaded: {self.files_downloaded}")
            return self.files_downloaded

        except Exception as e:
            logger.error(f"Error in download_course_files: {e}")
            return self.files_downloaded
        finally:
            self.cleanup()
        

if __name__ == "__main__":
    scraper = BlackboardScraper()
    if scraper.login("d.huamanor", "123@Pato"):
        total = scraper.download_course_files()
        print(f"Downloaded {total} files.")
