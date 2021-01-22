from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from webdriver_manager.firefox import GeckoDriverManager

import string
import random
import time

# Run it in an OS with a gui
from multiprocessing import Process

server_ip = "https://192.168.26.3/"

threads = 3

iters = 15


def random_string(n):
  return ''.join(random.choice(string.ascii_uppercase) for i in range(n))


def loggedout_stress(driver):
  driver.get(server_ip + "index.php/2021/01")
  driver.get(server_ip + "index.php/category/uncategorized/")
  driver.get(server_ip + "index.php/2021/01/18/hello-world/")
  driver.get(server_ip + "?s=yeenus")
  driver.get(server_ip + "wp-login.php?loggedout=true")
  driver.get(server_ip + "wp-login.php?action=lostpassword")
  driver.get(server_ip + "wp-login.php")

  # Fill out and send comment form
  driver.get(server_ip + "index.php/2021/01/18/hello-world/#comment-1")

  _comment = driver.find_element_by_id("comment")
  _comment.send_keys(random_string(20))

  _author = driver.find_element_by_id("author")
  _author.send_keys("Tyrone")

  _email = driver.find_element_by_id("email")
  _email.send_keys("cookieappel@gmail.com")

  _submit = driver.find_element_by_id("submit")
  _submit.click()

  time.sleep(2)


def loggedin_stress(driver):
  driver.get(server_ip + "wp-login.php")

  # Log in
  _uname = driver.find_element_by_id("user_login")
  _uname.send_keys("heartbleeder")

  _pass = driver.find_element_by_id("user_pass")
  _pass.send_keys("password")

  _submit = driver.find_element_by_id("wp-submit")
  _submit.click()

  # Wait to ensure login finishes
  time.sleep(2)

  # Create a post
  driver.get(server_ip + "wp-admin/post-new.php")

  time.sleep(2)

  _mce = driver.find_element(By.XPATH, '//textarea[@aria-label=\'Add block\']')
  _mce.click()

  time.sleep(1)

  _mce0 = driver.find_element_by_id("mce_0")
  _mce0.send_keys(random_string(50))


  _expand_publish = driver.find_element(By.XPATH, '//button[@class=\'components-button editor-post-publish-panel__toggle is-button is-primary\']')
  _expand_publish.click()

  time.sleep(1)


  _publish = driver.find_element(By.XPATH, '//button[@class=\'components-button editor-post-publish-button is-button is-default is-primary is-large\']')
  _publish.click()

  time.sleep(2)

  

  # Delete the post
  driver.get(server_ip + "wp-admin/edit.php")

  time.sleep(2)

  _delete = driver.find_element(By.XPATH, '//a[@aria-label=\'Move “(no title)” to the Trash\']')
  driver.get(_delete.get_attribute("href"))

  time.sleep(2)

  _logout = driver.find_element(By.XPATH, '//a[text()=\'Log Out\'][@class=\'ab-item\']')
  driver.get(_logout.get_attribute("href"))


def test_loop(parity = 0):
  # Install driver on the fly to avoid needing to configure path
  driver = webdriver.Firefox(executable_path=GeckoDriverManager().install())

  for i in range(0, iters):
    if parity == 0:
      loggedout_stress(driver)
      loggedin_stress(driver)
    else:
      loggedin_stress(driver)
      loggedout_stress(driver)

  print("loop done!")

  driver.close()


if __name__ == "__main__":
  # Spawn driver threads

  ps = []

  for i in range(0, threads):
    p = Process(target=test_loop, args=[i % 2])
    p.start()
    ps.append(p)

    time.sleep(2)

  for p in ps:
    p.join()