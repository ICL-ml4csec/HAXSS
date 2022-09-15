import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import ElementClickInterceptedException, InvalidSelectorException,\
	ElementNotInteractableException, StaleElementReferenceException, UnexpectedAlertPresentException, \
	NoAlertPresentException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
import random
import string
from functools import reduce
from functools import reduce
import time
import numpy as np
from selenium.webdriver.common.action_chains import ActionChains

class Crawler:
	def __init__(self, domain=None, browser='chrome', login_details=None):
			self.browser = browser
			self.input_names = []
			#self.to_strip = {}
			if domain is not None:
				if domain.count('/') > 3 or domain[-1] != '/':
					self.domain = ''
					for domain_component in domain.split('/'):
						if self.domain.count('/') < 3:
							self.domain += domain_component + '/'
				else:
					self.domain = domain
				self.transition_matrix = np.ndarray((1, 1), dtype=int)
				self.transition_matrix[0] = 0
				self.internal_urls = [domain]
				self.urls_with_login = []
				self.external_urls = []
				# key by input string, value by list of input url, and input element
				self.input_space = {}
				# key by username, value by password
				if login_details is not None:
					self.current_login = login_details
				else:
					self.current_login = {}
				self.login_details = []
				# where inputs go in and come out  dim0 = in, dim1 = out
				self.input_transitions = np.ndarray((1,1), dtype=int)
				self.input_transitions[0] = 0
				self.input_transition_tags = np.ndarray((1, 1), dtype=object)
				self.input_transition_tags[0] = ''
				self.injected = False
				self.crawl_sess = self._instansiate_crawl_sess(self.browser)
				#self.crawl_sess.get(self.domain)
				self._get_page(self.domain)
				# each value is an dict of [tag_name:, tag_text:, name:, value:]
				self.tags_that_transition = np.ndarray((1,1), dtype=object)
				self.tags_that_transition[0] = ''
				# index 0 requires login to access page dim0 = in
				self.features = np.ndarray((1, 3), dtype=int, buffer=np.array([0,0,0]))
				# key by url, value by tag 'name'
				self.file_uploads = {}

				self.logged_in = {self.domain:False}
				if self.crawl_sess.current_url != self.domain:
					self._login(self.crawl_sess.current_url)
				self.admin_login = False
				self.admin_dict = [login.split(':') for login in open('./crawling/admin_dict.txt').read().split('\n')]
			else:
				print('Domain not specified...')

	def _instansiate_crawl_sess(self, browser):
		if browser == 'chrome':
			options = webdriver.ChromeOptions()
			#options.add_argument('--headless')
			options.add_argument('--no-sandbox')
			options.add_argument('--disable-gpu')
			options.add_argument('--disable-dev-shm-usage')
			options.add_argument('--window-size=1920, 1080')
			driver = webdriver.Chrome(options=options)
		elif browser == 'firefox':
			options = webdriver.FirefoxOptions()
			#options.add_argument('-headless')
			driver = webdriver.Firefox(options=options)
		driver.set_page_load_timeout(5)
		return driver

	def close(self):
		self.crawl_sess.quit()

	def _get_page(self, url):
		self.crawl_sess.get(url)
		#WebDriverWait(self.crawl_sess, timeout=0.5) \
		#		.until(EC.element_to_be_clickable(
		#	(By.XPATH, '//input[@type="password"]/ancestor::div/descendant::input[@type="submit"]'))).click()
		self._dismiss_alerts()

	def _dismiss_alerts(self):
		no_payloads = False
		while no_payloads == False:
			try:
				time.sleep(0.2)
				self.crawl_sess.switch_to.alert.accept()
			except NoAlertPresentException:
				no_payloads = True


	def _check_url_is_new_page(self, url_without_input):
		# check if end url is already seen (e.g. is a comment on a page)
		is_page_pointer = any(self.crawl_sess.current_url.split('#')[0] == internal_url for internal_url in self.internal_urls)
		param_change_page = self.crawl_sess.current_url.split('?')[0].split('/')[-1]
		if param_change_page != '':
			#is_page_param_change = any(param_change_page == internal_url for internal_url in self.internal_urls)
			is_page_param_change = any(self.crawl_sess.current_url.split('?')[0] in internal_url for internal_url in self.internal_urls)

		else:
			is_page_param_change = False
		return not is_page_param_change and not is_page_pointer and all(re.search(url_without_input, url) is None for url in self.internal_urls)

	def _get_tag_info(self, tag):
		return {'tag_name': tag.tag_name, 'tag_text': tag.text,
					'name': tag.get_attribute('name') if tag.get_attribute('name') is not None else '',
					'value': tag.get_attribute('value') if tag.get_attribute(
						'value') is not None else ''}

	def _add_new_value(self, matrix, init_val, input, current_url, features=False, output_url=None):
		output_url = self.crawl_sess.current_url if output_url is None else output_url
		matrix = np.append(matrix, [[init_val for _ in range(matrix.shape[1])]], axis=0)
		if not features:
			matrix = np.append(matrix,[[init_val] for _ in range(matrix.shape[0])], axis=1)
			matrix[self.internal_urls.index(current_url)][self.internal_urls.index(output_url)] = input
		else:
			matrix[self.internal_urls.index(output_url)][0] = input
		return matrix

	def _update_features(self, matrix, input, input_url, feature):
		matrix[self.internal_urls.index(input_url)][feature] = input
		return matrix

	def _update_value(self, matrix, input, input_url, output_url=None):
		if output_url is None:
			output_url = self.crawl_sess.current_url
		try:
			current_value = matrix[self.internal_urls.index(input_url)][self.internal_urls.index(output_url)]
		except:
			pass
		if type(current_value) == dict and input_url in current_value.keys():
			if  not (any(current_value[input_url][i]['tag_name'] == input[input_url][0]['tag_name'] for i in range(len(current_value[input_url]))) and \
			    any(current_value[input_url][i]['name'] == input[input_url][0]['name'] for i in range(len(current_value[input_url]))) and \
			    any(current_value[input_url][i]['tag_text'] == input[input_url][0]['tag_text'] for i in range(len(current_value[input_url])))):
					current_value[input_url].append(input[input_url][0])
					matrix[self.internal_urls.index(input_url)][self.internal_urls.index(output_url)] = current_value
		else:
			matrix[self.internal_urls.index(input_url)][self.internal_urls.index(output_url)] = input
		return matrix

	def attempt_login(self):
		for url in self.internal_urls:
			self._get_page(url)
			if re.search('login', url, re.IGNORECASE) or \
					len(self.crawl_sess.find_elements_by_xpath('//*[translate(@type,\'ABCDEFGHIJKLMNOPQRSTUVWXYZ\',\'abcdefghijklmnopqrstuvwxyz\') = \'password\']')) == 1 and \
					len(self.crawl_sess.find_elements_by_xpath('//*[translate(@type,\'ABCDEFGHIJKLMNOPQRSTUVWXYZ\',\'abcdefghijklmnopqrstuvwxyz\') = \'password\']/../../*[@name="username"]')) > 0:
				#self.crawl_sess.get(url)
				for element in self.crawl_sess.find_elements_by_tag_name('a'):
					if re.search('create|register|sign up', element.text, re.IGNORECASE):
						element.click()
						break
				if re.search('admin', url, re.IGNORECASE):
						login_success = False
						for login in self.admin_dict:
							for input_element in self.crawl_sess.find_elements_by_xpath('//input'):
								if input_element.get_attribute('type') == 'password':
									input_element.send_keys(login[1])
								elif input_element.get_attribute('type') == 'checkbox' or input_element.get_attribute('type') == 'hidden':
									pass
								else:
									input_element.send_keys(login[0])
							try:
								self.crawl_sess.find_element_by_xpath('//input[translate(@type,\'ABCDEFGHIJKLMNOPQRSTUVWXYZ\',\'abcdefghijklmnopqrstuvwxyz\') = \'submit\']').click()
							except TimeoutException:
								pass
							if (self.crawl_sess.current_url != url and len(self.crawl_sess.find_elements_by_xpath('//*[translate(@type,\'ABCDEFGHIJKLMNOPQRSTUVWXYZ\',\'abcdefghijklmnopqrstuvwxyz\') = \'password\']')) == 0) \
									or re.search('logout', self.crawl_sess.page_source, re.I):
								# self.crawl_sess.get(url)
								login_success = True
								self.admin_dict = [login[0], login[1]]
								self.admin_login = True
								self.login_details.append({url:self.admin_dict})
								break
						if not login_success:
							if self.current_login is not None and type(self.current_login) == list:
								login_detail = self.current_login
								self.current_login = {url: login_detail}
								logged_in = self._login(url)
								if logged_in == True:
									# if self._check_url_is_new_page():
									#	self.internal_urls.append(self.crawl_sess.current_url)
									#	self.transition_matrix = self._add_new_value(self.transition_matrix, 0, 1, url)
									#	self.input_transitions = self._add_new_value(self.input_transitions, 0, 0, url)
									#	self.input_transition_tags = self._add_new_value(self.input_transition_tags, '', '', url)
									#	self.tags_that_transition = self._add_new_value(self.tags_that_transition, '', tag_info, url)
									self.logged_in[list(self.logged_in)[0]] = True
									if self.current_login not in self.login_details:
										self.login_details.append(self.current_login)
									return
				else:
					if self.current_login is not None and type(self.current_login) == list:
						login_detail = self.current_login
						self.current_login = {url: login_detail}
						logged_in = self._login(url)
						if logged_in == True:
							#if self._check_url_is_new_page():
							#	self.internal_urls.append(self.crawl_sess.current_url)
							#	self.transition_matrix = self._add_new_value(self.transition_matrix, 0, 1, url)
							#	self.input_transitions = self._add_new_value(self.input_transitions, 0, 0, url)
							#	self.input_transition_tags = self._add_new_value(self.input_transition_tags, '', '', url)
							#	self.tags_that_transition = self._add_new_value(self.tags_that_transition, '', tag_info, url)
							self.logged_in[list(self.logged_in)[0]] = True
							if self.current_login not in self.login_details:
								self.login_details.append(self.current_login)
							return
					self.current_login = {}
					try:
						input_tags = self.crawl_sess.find_elements_by_xpath("//input[translate(@type,\'ABCDEFGHIJKLMNOPQRSTUVWXYZ\',\'abcdefghijklmnopqrstuvwxyz\') = \'password\']/ancestor::div")[-3].find_elements_by_xpath('.//input')
					except:
						try:
							input_tags = self.crawl_sess.find_elements_by_xpath("//input[translate(@type,\'ABCDEFGHIJKLMNOPQRSTUVWXYZ\',\'abcdefghijklmnopqrstuvwxyz\') = \'password\']/ancestor::div")[-2].find_elements_by_xpath('.//input')
						except:
							try:
								input_tags = self.crawl_sess.find_elements_by_xpath("//input[translate(@type,\'ABCDEFGHIJKLMNOPQRSTUVWXYZ\',\'abcdefghijklmnopqrstuvwxyz\') = \'password\']/ancestor::div")[-1].find_elements_by_xpath('.//input')
							except:
								return False
					for input_element in input_tags:
						if input_element.get_attribute('type') == 'password':
							if url in self.current_login.keys() \
									and self.current_login[url][1] != '':
								input_element.send_keys(self.current_login[url][1])
							else:
								pword = ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase) for _ in range(6))
								input_element.send_keys(pword)
								self.current_login[url][1] = pword

								self.input_space[pword] = [self.crawl_sess.current_url, self._get_tag_info(input_element)]
						elif input_element.get_attribute('name') == 'username':
							if url in self.current_login.keys() \
									and self.current_login[url][0] != '':
								input_element.send_keys(self.current_login[url][0])
							else:
								usrname = ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase) for _ in range(6))
								input_element.send_keys(usrname)
								self.input_space[usrname] = [self.crawl_sess.current_url, self._get_tag_info(input_element)]
								self.current_login[url] = [usrname, '']
						elif 'email' in input_element.get_attribute('name'):
							if url in self.current_login.keys() \
									and self.current_login[url][0] != '':
								input_element.send_keys(self.current_login[url][0])
							else:
								usrname = ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase) for _ in range(6)) +'@email.com'
								input_element.send_keys(usrname)
								#self.input_space[usrname] = [self.crawl_sess.current_url, self._get_tag_info(input_element)]
								self.current_login[url] = [usrname, '']
						else:
							rand_string = ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase) for _ in range(6))
							input_element.send_keys(rand_string)
							self.input_space[rand_string] = [self.crawl_sess.current_url, self._get_tag_info(input_element)]
					time.sleep(3)
					try:
						WebDriverWait(self.crawl_sess, timeout=0.5) \
							.until(EC.element_to_be_clickable((By.XPATH, '//input[@type="password"]/ancestor::div/descendant::input[@type="submit"]'))).click()
					except:
						WebDriverWait(self.crawl_sess, timeout=0.5) \
							.until(EC.element_to_be_clickable(
							(By.XPATH,
							 '//input[@type="password"]/ancestor::div/descendant::button[contains(@*, "login")]'))).click()
					self._login(url)
					self.logged_in[url] = True
		self.login_details.append(self.current_login)

	def _login(self, url):
		for key, val in self.logged_in.items():
			if val == True and url==key:
				url = key
		#self.crawl_sess.get(url)
		self._get_page(url)
		if len(self.current_login) == 0:
			return False
		try:
			input_tags = self.crawl_sess.find_elements_by_xpath('//input[translate(@type,\'ABCDEFGHIJKLMNOPQRSTUVWXYZ\',\'abcdefghijklmnopqrstuvwxyz\') = \'password\']/ancestor::div')[-3].find_elements_by_xpath('.//input')
		except:
			try:
				input_tags = self.crawl_sess.find_elements_by_xpath('//input[translate(@type,\'ABCDEFGHIJKLMNOPQRSTUVWXYZ\',\'abcdefghijklmnopqrstuvwxyz\') = \'password\']/ancestor::div')[-2].find_elements_by_xpath('.//input')
			except:
				try:
					input_tags = self.crawl_sess.find_elements_by_xpath('//input[translate(@type,\'ABCDEFGHIJKLMNOPQRSTUVWXYZ\',\'abcdefghijklmnopqrstuvwxyz\') = \'password\']/ancestor::div')[-1].find_elements_by_xpath('.//input')
				except:
					return True
		for tag in input_tags:
			if ('username' in tag.get_attribute('name') or 'user' in tag.get_attribute('name')  or 'login' in tag.get_attribute('name') or 'login' in tag.get_attribute('id')) and re.search('password|hidden|checkbox', tag.get_attribute('type'), re.I) is None:
				tag.send_keys(self.current_login[url][0])
			elif 'email' in tag.get_attribute('name'):
				tag.send_keys(self.current_login[url][0])
			if 'password' in tag.get_attribute('name') or tag.get_attribute('type') == 'password':
				tag.send_keys(self.current_login[url][1])
		try:
			login_submit = self.crawl_sess.find_element_by_xpath("//input[translate(@type,\'ABCDEFGHIJKLMNOPQRSTUVWXYZ\',\'abcdefghijklmnopqrstuvwxyz\') = \'password\']/ancestor::div//*[translate(@type,\'ABCDEFGHIJKLMNOPQRSTUVWXYZ\',\'abcdefghijklmnopqrstuvwxyz\') = \'submit\']")
		except:
			login_submit = self.crawl_sess.find_element_by_xpath('//button[contains(@*, "login")]')
		login_submit_value = login_submit.get_attribute('value')
		login_submit_text = login_submit.text
		login_submit.click()
		if len(self.crawl_sess.find_elements_by_xpath('//*[@value="'+login_submit_value+'"]')) == 0 or (len(login_submit_text) > 1 and login_submit_text in self.crawl_sess.page_source):
			return True
		else:
			return False
		#self.crawl_sess.get(url)
		#if self.crawl_sess.page_source == unlogged_source:
		#	self.attempt_login()
		#return self.crawl_sess

	def _check_url(self, current_url, tag_info, input=None):
		# new site, not an error page and in the search domain
		if current_url != self.crawl_sess.current_url and self.domain in self.crawl_sess.current_url \
				and 'HTTP ERROR' not in self.crawl_sess.page_source:
			# check page not seen before and is not the same webpage
			search_safe_url = self.crawl_sess.current_url
			if input is not None:
				for var in input:
					search_safe_url =  re.sub(var, '', search_safe_url)
			search_url_in_internals =  not all(search_safe_url not in url for url in self.internal_urls)
			if input is not None and search_url_in_internals == False:
				new_url = search_safe_url
				print('new page found: ' + new_url)

				self.internal_urls.append(new_url)
				self.transition_matrix = self._add_new_value(self.transition_matrix, 0, 1, current_url, output_url=new_url)
				self.input_transitions = self._add_new_value(self.input_transitions, 0, 0, current_url, output_url=new_url)
				self.input_transition_tags = self._add_new_value(self.input_transition_tags, '', '', current_url, output_url=new_url)
				self.tags_that_transition = self._add_new_value(self.tags_that_transition, '', tag_info, current_url, output_url=new_url)
				if any(val == True for val in self.logged_in.values()):
					self.features = self._add_new_value(self.features, 0, self.login_details.index(self.current_login) + 1 , current_url, features=True, output_url=new_url)
				else:
					self.features = self._add_new_value(self.features, 0, 0, current_url, features=True, output_url=new_url)
				return True
			elif input is not None and search_url_in_internals == True:
				if input is not None:
					new_url = search_safe_url
				else:
					new_url = self.crawl_sess.current_url
				#print('page found with new transition: ' + new_url)
				if new_url not in self.internal_urls:
					for url in self.internal_urls:
						if new_url in url:
							new_url = url
							break
				self.tags_that_transition = self._update_value(self.tags_that_transition, tag_info, current_url, output_url=new_url)
				self.transition_matrix = self._update_value(self.transition_matrix, 1, current_url, output_url=new_url)
				return False
			elif self.crawl_sess.current_url not in self.internal_urls and self._check_url_is_new_page(search_safe_url):
				print('new page found: ' + self.crawl_sess.current_url)
				self.internal_urls.append(self.crawl_sess.current_url)
				self.transition_matrix = self._add_new_value(self.transition_matrix, 0, 1, current_url)
				self.input_transitions = self._add_new_value(self.input_transitions, 0, 0, current_url)
				self.input_transition_tags = self._add_new_value(self.input_transition_tags, '', '', current_url)
				self.tags_that_transition = self._add_new_value(self.tags_that_transition, '', tag_info, current_url)
				if any(val == True for val in self.logged_in.values()):
					self.features = self._add_new_value(self.features, 0,  self.login_details.index(self.current_login) + 1 , current_url, features=True)
				else:
					self.features = self._add_new_value(self.features, 0, 0, current_url, features=True)
				return True
			elif self.crawl_sess.current_url in self.internal_urls:
				self.tags_that_transition = self._update_value(self.tags_that_transition, tag_info, current_url)
				self.transition_matrix = self._update_value(self.transition_matrix, 1, current_url)
				print('page found with new transition: ' + self.crawl_sess.current_url)
				return False
			else:
				print('same page found: ' + self.crawl_sess.current_url)
				found_url = self.crawl_sess.current_url
				for url in self.internal_urls:
					if url in self.crawl_sess.current_url:
						found_url = url
				return False

	def _is_not_legit_page(self, url):
		#self.crawl_sess.get(url)
		self._get_page(url)
		if 'HTTP ERROR' in self.crawl_sess.page_source or self.crawl_sess.current_url != url:
			return True
		else:
			return False

	def _find_page_dependencies(self, url):
		url_dependencies = [self.internal_urls[i] for i in range(self.transition_matrix.shape[0]) if self.transition_matrix[i, self.internal_urls.index(url)] == 1]
		return url_dependencies

	def _get_page_from_dependency(self, dependency, target):
		transition_tag_info = self.tags_that_transition[self.internal_urls.index(dependency)][self.internal_urls.index(target)]
		input_tags = {}
		#self.crawl_sess.get(dependency)
		self._get_page(dependency)
		for rand_string, input_info in self.input_space.items():
			if dependency == input_info[0] and input_info[1] != transition_tag_info:
				if input_info[1]['name'] != '':
					element = self.crawl_sess.find_elements_by_xpath(
						'//' + input_info[1]['tag_name'] + '[@name="' + input_info[1]['name'] + '"]')
					if type(element) == list:
						try:
							element = element[0]
						except:
							pass
					else:
						new_target = dependency
						dependencies = self._find_page_dependencies(new_target)
						#self.crawl_sess.get(new_target)
						self._check_logged_in(new_target)
						self._get_page(new_target)
						for new_dependant in dependencies:
							self._get_page_from_dependency(new_dependant, new_target)
							#self.crawl_sess.get(target)
							self._get_page(target)
							if target == self.crawl_sess.current_url:
								return
					if type(element) != list and element.get_attribute('type') != 'hidden':
						element.send_keys(self.input_space[rand_string][1]['value'])
				elif input_info[1]['value'] != '':
					element = self.crawl_sess.find_elements_by_xpath(
						'//' + input_info[1]['tag_name'] + '[@value="' + input_info[1]['value'] + '"]')
					if len(element) == 0:
						new_target = dependency
						dependencies = self._find_page_dependencies(new_target)
						#self.crawl_sess.get(new_target)
						self._get_page(new_target)
						for new_dependant in dependencies:
							self._get_page_from_dependency(new_dependant, new_target)
							#self.crawl_sess.get(target)
							self._get_page(target)
							if target == self.crawl_sess.current_url:
								return
					else:
						element = element[0]
					try:
						element.get_attribute('type')
					except:
						pass
					if element.get_attribute('type') != 'hidden':
						try:
							element.send_keys(self.input_space[rand_string][1]['value'])
						except:
							print('element not interactable')
				input_tags[rand_string] = input_info[1]
		for key in transition_tag_info.keys():
			if transition_tag_info[key] != '' and key != 'tag_name':
				if key == 'tag_text':
					try:
						self.crawl_sess.find_element_by_xpath('//' + transition_tag_info['tag_name'] + '[contains(.,"' + transition_tag_info[key] + '")]').click()
					except:
						print('could not find submitable element')

				else:
					try:
						self.crawl_sess.find_element_by_xpath('//' + transition_tag_info['tag_name'] + '[@'+key+'="'+transition_tag_info[key]+'"]').click()
					except:
						print('could not resubmit to find page...')
		if self.crawl_sess.current_url != target and transition_tag_info['tag_name'] is not None:
			try:
				submit_element = self.crawl_sess.find_element_by_xpath('//form[.//' + transition_tag_info[
					'tag_name'] + ']//*[translate(@type,\'ABCDEFGHIJKLMNOPQRSTUVWXYZ\',\'abcdefghijklmnopqrstuvwxyz\') = \'submit\']')
				self.crawl_sess.execute_script("arguments[0].scrollIntoView();", submit_element)
				submit_element.click()
			except:
				print('cannot locate submit element...')
	def _check_logged_in(self, current_url):
		if any(val == True for val in self.logged_in.values()) and re.search('login|signin|sign in', self.crawl_sess.page_source, re.IGNORECASE):
			matches = re.findall('logout|signout|sign out', self.crawl_sess.page_source, re.IGNORECASE)
			logged_out = []
			for match in matches:
				try:
					self.crawl_sess.find_element_by_xpath('//*[text() = "' + match + '"]')
					logged_out.append(False)
				except:
					try:
						self.crawl_sess.find_element_by_xpath('//*[contains(@href,"' + match + '")] ')
						logged_out.append(False)
					except:
						logged_out.append(True)
					logged_out.append(True)
					pass
			if logged_out == []:
				if len(self.crawl_sess.find_elements_by_xpath('//*[contains(.,"Login")]')) > 0 or \
						len(self.crawl_sess.find_elements_by_xpath('//*[translate(@name,\'ABCDEFGHIJKLMNOPQRSTUVWXYZ\',\'abcdefghijklmnopqrstuvwxyz\')=\'login\']')) > 0 or \
						re.search('login|signin|sign in', self.crawl_sess.current_url, re.IGNORECASE):
					logged_out = [True]
				else:
					logged_out = [False]
			if not any(log_check == False for log_check in logged_out) and matches or logged_out == [True]:
				print('logged out...')
				self._login(list(self.current_login)[0])
				#self.crawl_sess.get(current_url)
				self._get_page(current_url)
	def get_current_url(self):
		current_url = self.crawl_sess.current_url
		if current_url not in self.internal_urls:
			for url in self.internal_urls:
				if re.search(current_url, url) is not None:
					current_url = url
		return current_url

	def crawl(self, discover_inputs=True):
		page_idx = 0
		#num_urls = len(self.internal_urls)
		while page_idx < len(self.internal_urls):
			current_url = self.internal_urls[page_idx]
			self._check_logged_in(current_url)
			print('\nsearching: ' + current_url+ '\n')


			if self._is_not_legit_page(current_url):
				page_dependency = self._find_page_dependencies(current_url)
				if len(self.internal_urls) == 1 and re.search('signin|signup|login', self.crawl_sess.current_url, re.I):
					self._check_url(current_url, '')
					current_url = self.get_current_url()
					tag_info = self._get_tag_info(self.crawl_sess.find_element_by_xpath('//input[@type="password"]/ancestor::*//*[@type="submit"]'))
					self.attempt_login()
					if self.crawl_sess.current_url not in self.internal_urls or self.crawl_sess.current_url != current_url:
						self._check_url(current_url, tag_info)
						current_url = self.get_current_url()
				else:
					try:
						self._get_page_from_dependency(page_dependency[0], current_url)
						self.crawl_sess.refresh()
					except:
						page_idx += 1
						continue
			a_tags = self.crawl_sess.find_elements_by_tag_name('a')
			is_new_page = False
			for idx in range(len(a_tags)):
				self._check_logged_in(current_url)
				if self._is_not_legit_page(current_url):
					page_dependency = self._find_page_dependencies(current_url)
					self._get_page_from_dependency(page_dependency[0], current_url)

				a_tags = self.crawl_sess.find_elements_by_tag_name('a')
				try:
					tag = a_tags[idx]
				except:
					continue
				try:
					tag_info = self._get_tag_info(tag)
					# check not signout/logout also check the href does not lead to outside the domain
					tag_info_string = ''.join(tag_info.values())
					if not re.search('logout|signout|sign out', tag_info_string, re.IGNORECASE) and \
							tag.get_attribute('href') is not None and self.domain in tag.get_attribute('href') and \
							re.search('delete|remove', tag.get_attribute('text'), re.IGNORECASE) is None:
						try:
							tag.click()
						except TimeoutException:
							pass
						try:
							self.crawl_sess.current_url
						except UnexpectedAlertPresentException:
							pass

					# if href does lead to outside the domain, then add to external pages
					elif tag.get_attribute('href') is not None and self.domain not in tag.get_attribute('href'):
						if self.crawl_sess.current_url not in self.external_urls:
							print('external page found: ' + tag.get_attribute('href'))
							self.external_urls.append(tag.get_attribute('href'))

					is_new_page = self._check_url(current_url, tag_info)

				except ElementClickInterceptedException:
					print('element not on page')
					pass
				except ElementNotInteractableException:
					print('element not interactable')
					if not tag.is_displayed() and tag.is_enabled():
						parent_element = tag.find_element_by_xpath('..')
						try:
							while not tag.is_displayed():
								try:
									parent_element.click()
								except:
									pass
								try:
									parent_element = parent_element.find_element_by_xpath('..')
								except InvalidSelectorException:
									break

								a_tags = self.crawl_sess.find_elements_by_tag_name('a')
								tag = a_tags[idx]
								if parent_element == self.crawl_sess.find_element_by_xpath('/*'):
									break
						except:

							print('error')

					if self.crawl_sess.current_url != current_url:
						self._get_page(current_url)
						a_tags = self.crawl_sess.find_elements_by_tag_name('a')
						try:
							tag = a_tags[idx]
						except:
							time.sleep(3)
							self._get_page(current_url)
							a_tags = self.crawl_sess.find_elements_by_tag_name('a')
							tag = a_tags[idx]
					try:
						tag.is_displayed()
					except:
						a_tags = self.crawl_sess.find_elements_by_tag_name('a')
						tag = a_tags[idx]
					if tag.is_displayed():
						ActionChains(self.crawl_sess).move_to_element(tag).click()
						is_new_page = self._check_url(current_url, tag_info)
					else:
						try:
							ActionChains(self.crawl_sess).move_to_element(tag).click()
						except:
							pass
				try:
					tag.get_attribute('href')
				except:
					time.sleep(3)
					self._check_logged_in(current_url)
					self._get_page(current_url)
					a_tags = self.crawl_sess.find_elements_by_tag_name('a')
					try:
						tag = a_tags[idx]
					except:
						if self._is_not_legit_page(current_url):
							page_dependency = self._find_page_dependencies(current_url)
							if len(self.internal_urls) == 1 and re.search('signin|signup|login', self.crawl_sess.current_url,
																		  re.I):
								self._check_url(current_url, '')
								# self.internal_urls.append(self.crawl_sess.current_url)
								current_url = self.get_current_url()
								tag_info = self._get_tag_info(self.crawl_sess.find_element_by_xpath(
									'//input[@type="password"]/ancestor::*//*[@type="submit"]'))
								self.attempt_login()
								if self.crawl_sess.current_url not in self.internal_urls or self.crawl_sess.current_url != current_url:
									self._check_url(current_url, tag_info)
									current_url = self.get_current_url()
							else:
								try:
									self._get_page_from_dependency(page_dependency[0], current_url)
									self.crawl_sess.refresh()
								except:
									print('could not route to page...')
									page_idx += 1
									continue
						a_tags = self.crawl_sess.find_elements_by_tag_name('a')
						tag = a_tags[idx]

				if tag.get_attribute('href') is not None and self.domain in tag.get_attribute('href') and re.search('delete|remove',  tag.get_attribute('href'), re.I) is None:
					#self.crawl_sess.get(tag.get_attribute('href'))
					self._get_page(tag.get_attribute('href'))
				elif tag.get_attribute('href') is not None and 'http' not in tag.get_attribute('href') and re.search('delete|remove',  tag.get_attribute('href'), re.I) is None:
					try:
						if tag.get_attribute('href')[0] == '/':
							self._get_page(self.domain + tag.get_attribute('href')[1:])
						# self.crawl_sess.get(self.domain + tag.get_attribute('href')[1:])
						else:
							self._get_page(self.domain + tag.get_attribute('href'))
						#self.crawl_sess.get(self.domain + tag.get_attribute('href')
					except:
						print('error page with badly formatted href')
				is_new_page = self._check_url(current_url, tag_info)

			self._get_page(current_url)

			if len(self.crawl_sess.find_elements_by_xpath('//form//option')) > 0:
				option_tags = self.crawl_sess.find_elements_by_xpath('//form//option')
				for idx in range(len(option_tags)):
					if self._is_not_legit_page(current_url):
						page_dependency = self._find_page_dependencies(current_url)

					self._check_logged_in(current_url)
					option_tags = self.crawl_sess.find_elements_by_xpath('//form//option')
					try:
						tag = option_tags[idx]
					except:
						time.sleep(3)
						self._get_page(current_url)
						option_tags = self.crawl_sess.find_elements_by_xpath('//form//option')
						try:
							tag = option_tags[idx]
						except:
							pass
					try:
						tag_info = self._get_tag_info(tag)
						tag_info_string = ''.join(tag_info.values())
						if not re.search('logout|signout|sign out', tag_info_string, re.IGNORECASE) and \
							re.search('delete|remove', tag.get_attribute('text'), re.IGNORECASE) is None \
								and re.search('privilege|delete|remove', tag.find_elements_by_xpath('parent::select')[0].get_attribute('name'), re.I) is None:
							self.crawl_sess.execute_script("arguments[0].scrollIntoView();", tag)
							tag.is_displayed()
							try:
								tag.click()
							except:
								continue
							try:
								submit_tag = tag.find_element_by_xpath('.//ancestor::form[.//'+tag_info['tag_name']+'[@value = "'+tag_info['value']+'"]]//*[translate(@type,\'ABCDEFGHIJKLMNOPQRSTUVWXYZ\',\'abcdefghijklmnopqrstuvwxyz\') = \'submit\']')
							except:
								try:
									submit_tag = tag.find_element_by_xpath('.//ancestor::form[.//'+tag_info['tag_name']+'[text() = "'+tag_info['value']+'"]]//*[translate(@type,\'ABCDEFGHIJKLMNOPQRSTUVWXYZ\',\'abcdefghijklmnopqrstuvwxyz\') = \'submit\']')
								except:
									try:
										submit_tag = tag.find_element_by_xpath('.//ancestor::form[.//'+tag_info['tag_name']+']//*[translate(@type,\'ABCDEFGHIJKLMNOPQRSTUVWXYZ\',\'abcdefghijklmnopqrstuvwxyz\') = \'submit\']')
									except:
										try:
											submit_tag = tag.find_element_by_xpath('.//ancestor::form[.//' + tag_info['tag_name'] + ']//*[translate(@value,\'ABCDEFGHIJKLMNOPQRSTUVWXYZ\',\'abcdefghijklmnopqrstuvwxyz\') = \'submit\']')
										except:
											submit_tag = None
							if submit_tag is not None:
								submit_tag.is_displayed()
								self.crawl_sess.execute_script("arguments[0].scrollIntoView();", submit_tag)
								submit_tag.click()
						is_new_page = self._check_url(current_url, tag_info)

					except ElementClickInterceptedException:
						print('element not on page')
						pass
					except ElementNotInteractableException:
						print('element not interactable')
						if not tag.is_displayed() and tag.is_enabled():
							parent_element = tag.find_element_by_xpath('..')
							while not tag.is_displayed():
								try:
									parent_element.click()
								except:
									pass
								parent_element = parent_element.find_element_by_xpath('..')
								if parent_element == self.crawl_sess.find_element_by_xpath('/*'):
									break
						if tag.is_displayed():
							tag.click()
							is_new_page = self._check_url(current_url, tag_info)
					except StaleElementReferenceException:
						print('stale element')
			if self._is_not_legit_page(current_url):
				page_dependency = self._find_page_dependencies(current_url)
				self._get_page_from_dependency(page_dependency[0], current_url)
			if (self.crawl_sess.find_elements_by_xpath('//input') or self.crawl_sess.find_elements_by_xpath('//textarea')) and discover_inputs == True:
				try:
					self._discover_inputs(current_url)
					if all(self.input_transitions[self.internal_urls.index(self.crawl_sess.current_url)] == 0):
						self._discover_url_inputs(current_url)
				except:
					print('error has occured in input detection')
			elif is_new_page:
				self._discover_url_inputs(current_url)
				self._discover_inputs(current_url)
			elif '?' in self.crawl_sess.current_url and discover_inputs == True:
				self._discover_url_inputs(current_url)


			page_idx += 1


		#print(self.input_transitions)
		print('External URLs  found:')
		print(self.external_urls)
		print('Internal URLs found: ')
		print(self.internal_urls)
		#print(self.transition_matrix)
		#print(self.features)

	def _check_inputs_on_page(self, page_dependency=None, tag_info=None, current_url=None):
		if any(re.search(input_string, self.crawl_sess.page_source, re.I) for input_string in self.input_space.keys()):
			for rand_string in self.input_space.keys():
				if re.search(rand_string, self.crawl_sess.page_source, re.I):
					if 'search' in self.crawl_sess.current_url:
						out_url = re.sub(rand_string, '', self.crawl_sess.current_url)
						out_url_from_list = [url for url in self.internal_urls if out_url in url]
						if len(out_url_from_list) > 0:
							out_url = out_url_from_list[0]
					else:
						out_url = self.crawl_sess.current_url
						if out_url not in self.internal_urls:
							out_url = [url for url in self.internal_urls if url in self.crawl_sess.current_url and url not in self.domain]
							if len(out_url) > 0:
								out_url = out_url[0]
							else:
								simple_url = self.crawl_sess.current_url.split('#')[0].split('?')[0]
								out_url = [url for url in self.internal_urls if simple_url in url][0]

					if tag_info != None and out_url != current_url and current_url != page_dependency:
						update = {self.input_space[rand_string][0]:[self.input_space[rand_string][1]], current_url: [tag_info]}
					else:
						update = {self.input_space[rand_string][0]:[self.input_space[rand_string][1]]}
					prior_transition = self.input_transitions[self.internal_urls.index(self.input_space[rand_string][0])][self.internal_urls.index(out_url)]
					self.input_transitions = self._update_value(self.input_transitions, 1,
																input_url=self.input_space[rand_string][0],
																output_url=out_url)
					if any(val == True for val in self.logged_in.values()) and \
							self.input_space[rand_string][0] == current_url:
						self.features = self._update_features(self.features, self.login_details.index(self.current_login) + 1, out_url, 0)


					self.input_transition_tags = self._update_value(self.input_transition_tags, update,
																	input_url=self.input_space[rand_string][0],
																	output_url=out_url)


	def _check_page_after_input(self, current_url, tag_info, form_idx, form_element, input_elements, string, page_dependency=None):
		self.crawl_sess.page_source
		if 'HTTP ERROR' not in self.crawl_sess.page_source:
			if current_url != self.crawl_sess.current_url:
				self._check_url(current_url, tag_info, input=[string])
				# check if any input is present on the page
				if self.domain in self.crawl_sess.current_url:
					self._check_inputs_on_page(page_dependency, tag_info, current_url)
					self.crawl_sess.refresh()
					self._dismiss_alerts()
					self._check_inputs_on_page(page_dependency, tag_info, current_url)
				if self._is_not_legit_page(current_url):
					dependencies = self._find_page_dependencies(current_url)
					for dependency in dependencies:
						self._get_page_from_dependency(dependency, current_url)
				try:
					form_element = self.crawl_sess.find_elements_by_xpath('//form')[form_idx]
					input_elements = form_element.find_elements_by_xpath('.//input') + form_element.find_elements_by_xpath('.//textarea')
				except:
					time.sleep(3)
					form_element = self.crawl_sess.find_elements_by_xpath('//form')[form_idx]
					input_elements = form_element.find_elements_by_xpath('.//input') + form_element.find_elements_by_xpath('.//textarea')
			else:
				# check if any input is present on the page
				self._check_inputs_on_page(page_dependency, tag_info, current_url)
				self.crawl_sess.refresh()
				self._dismiss_alerts()
				self._check_inputs_on_page(page_dependency, tag_info, current_url)
		else:
			self.input_space.pop(string)
			if self._is_not_legit_page(current_url):
				self._get_page_from_dependency(page_dependency, current_url)
			form_element = self.crawl_sess.find_elements_by_xpath('//form')[form_idx]
			input_elements = form_element.find_elements_by_xpath('.//input') + form_element.find_elements_by_xpath('.//textarea')
		return form_element, input_elements

	def _submit_string_to_element(self, elements, idx, form_idx, current_url, submit_element, submit_all, form, page, page_source, transition_tag_info, displays, enter=False):
		rand_string = ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase) for _ in range(6))
		if not re.search('token', elements[idx].get_attribute('name'), re.IGNORECASE) \
				and all(re.search('login', elements[i].get_attribute('name'), re.IGNORECASE) == None for i in
						range(len(elements))) \
				and 'login' not in self.crawl_sess.current_url and 'register' not in self.crawl_sess.current_url and 'url' not in elements[idx].get_attribute('name'):

			# check if value attriute present in tag and then change the value
			if elements[idx].get_attribute('value') != '' \
					and elements[idx].get_attribute('type') != 'submit':
				self.input_space[rand_string] = [current_url, self._get_tag_info(elements[idx])]
				if self._get_tag_info(elements[idx])['tag_name'] == 'textarea':
					try:
						idx_bound = len(self.crawl_sess.execute_script("form_nodes = document.evaluate('//form', document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);var display_list = []; for (var i = 0; i < form_nodes.snapshotLength; i++) { var node_list = []; input_nodes = document.evaluate('.//descendant::"+elements[idx].tag_name+"', form_nodes.snapshotItem(i), null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null); for (var j = 0; j < input_nodes.snapshotLength; j++) {  node_list[j] = window.getComputedStyle(input_nodes.snapshotItem(j)).display} display_list[i] = node_list} return node_list"))
						self.crawl_sess.execute_script("document.getElementsByTagName('"+self._get_tag_info(elements[idx])['tag_name']+"')[" + str(
							idx_bound -1) + "].value='" + rand_string + "';")
					except:
						pass
				else:
					self.crawl_sess.execute_script(
						"document.getElementsByTagName('" + self._get_tag_info(elements[idx])['tag_name'] + "')[" + str(
							reduce(lambda count, l: count + len(l), displays[:form_idx],
								   0) + idx) + "].value='" + rand_string + "';")
			# check if the input element is displayed on the page and that it is not a file upload
			if elements[idx] != 'none' and \
					elements[idx].get_attribute('type') != 'file' and \
					elements[idx].get_attribute('type') != 'hidden':
				if 'email' in elements[idx].get_attribute('name'):
					elements[idx].send_keys(rand_string + '@email.com')
				elif (elements[idx].get_attribute('type') == 'password' or re.search('password',elements[idx].get_attribute('name'), re.I)) and re.search('add.user', self.crawl_sess.page_source, re.I) is None:
					pass
				elif elements[idx].get_attribute('class') != 'hidden':
					try:
						elements[idx].send_keys(rand_string)
					except:
						if elements[idx].is_displayed() == False:
							if len(self.crawl_sess.find_elements_by_xpath('//'+elements[idx].tag_name+'[@name="'+elements[idx].get_attribute('name')+'"]//ancestor::div//*[@type="checkbox"]')) >0:
								try:
									self.crawl_sess.find_elements_by_xpath(
										'//' + elements[idx].tag_name + '[@name="' + elements[idx].get_attribute(
											'name') + '"]//ancestor::div//*[@type="checkbox"]')[0].click()
								except:
									print('checkbox not interactable')
									pass
								if elements[idx].is_displayed() == True:
									elements[idx].send_keys(rand_string)

				if rand_string not in self.input_space.keys():
					self.input_space[rand_string] = [current_url, self._get_tag_info(elements[idx])]

			elif elements[idx].get_attribute('type') == 'file':
				self.file_uploads[current_url] = elements[idx].get_attribute('name')

			if submit_all == False:
				time.sleep(0.5)
				try:
					submit_element.click()
				except:
					pass
				if enter == True:
					try:
						submit_element.send_keys(Keys.ENTER)
					except StaleElementReferenceException:
						pass
					except ElementNotInteractableException:
						pass
				self._dismiss_alerts()
				if self.crawl_sess.current_url == current_url and self.crawl_sess.page_source != page_source:
					page_change = str(
						set(self.crawl_sess.page_source.splitlines()) - set(page_source.splitlines()))

					if re.search('include|all|error|required', page_change, re.IGNORECASE) is not None:
						self._get_page(current_url)
						form = self.crawl_sess.find_elements_by_xpath('//form')[form_idx]
						if len(form.find_elements_by_xpath('.//input')) > 0:
							elements = form.find_elements_by_xpath('.//input') + \
									   form.find_elements_by_xpath('.//textarea')
						else:
							elements = form.find_elements_by_xpath('./ancestor::div')[-1].find_elements_by_xpath(
								'.//descendant::input') + \
									   form.find_elements_by_xpath('./ancestor::div')[-1].find_elements_by_xpath(
										   './/descendant::textarea')
						if elements[idx].get_attribute('type') != 'hidden':
							try:
								elements[idx].send_keys(rand_string)
							except:
								print('not interactable')
						submit_all = True
			elif self.crawl_sess.current_url not in self.urls_with_login:
				self.urls_with_login.append(self.crawl_sess.current_url)

		# check if a different url has been reached
		if current_url != self.crawl_sess.current_url:
			try:
				form, _ = self._check_page_after_input(current_url, transition_tag_info,
													   form_idx, form, elements, rand_string,
													   page_dependency=page)
				elements = form.find_elements_by_xpath('.//input') + form.find_elements_by_xpath(
					'.//textarea')
			except:
				print('element not attached...')
		else:
			if submit_all == False:
				try:
					self._check_inputs_on_page(page_dependency=page, tag_info=transition_tag_info, current_url=current_url)
					self.crawl_sess.refresh()
					self._dismiss_alerts()
					self._check_inputs_on_page(page_dependency=page, tag_info=transition_tag_info, current_url=current_url)
					form.is_enabled()
				except StaleElementReferenceException:
					self._get_page(current_url)
					form = self.crawl_sess.find_elements_by_xpath('//form')[form_idx]
					if len(form.find_elements_by_xpath('.//input')) > 0:
						elements = form.find_elements_by_xpath('.//input') + form.find_elements_by_xpath('.//textarea')
					elif len(form.find_elements_by_xpath('./ancestor::div')) > 0:
						elements = form.find_elements_by_xpath('./ancestor::div')[-1].find_elements_by_xpath('.//descendant::input') + form.find_elements_by_xpath('./ancestor::div')[-1].find_elements_by_xpath('.//descendant::textarea')
					else:
						elements = form.find_elements_by_xpath('./ancestor::*')[-1].find_elements_by_xpath(
							'.//descendant::input') + form.find_elements_by_xpath('./ancestor::*')[-1].find_elements_by_xpath(
							'.//descendant::textarea')

		return form, elements, submit_all, rand_string

	def _discover_url_inputs(self, current_url):
		if self._is_not_legit_page(current_url):
			page_dependancies = self._find_page_dependencies(current_url)
		else:
			page_dependancies = [current_url]
		for page in page_dependancies:
			if self._is_not_legit_page(current_url):
				self._get_page_from_dependency(page, current_url)
			inital_source = self.crawl_sess.current_url
			if '=' in inital_source:
				inputs = inital_source.split('?')
				inputs = [input.split('=') for input in  inputs[1].split('&')]
				for input in inputs:
					rand_string = ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase) for _ in range(6))
					inputs[inputs.index(input)][1] = rand_string

				joined_inputs_list = ['='.join(entry) for entry in inputs]
				join_inputs = '&'.join(joined_inputs_list)
				url = inital_source.split('?')[0] + '?' + join_inputs
				self._get_page(url)
				tag_info = {'tag_name': 'URL', 'tag_text': 'GET',
				 'name':'',
				 'value': ''}
				self.input_space[rand_string] = [current_url, tag_info]

				if 'HTTP ERROR' not in self.crawl_sess.page_source:
					if current_url != self.crawl_sess.current_url:
						self._check_url(current_url, tag_info, input=[i[1] for i in inputs])

						self._check_inputs_on_page(page, tag_info, current_url)
						self.crawl_sess.refresh()
						self._dismiss_alerts()
						self._check_inputs_on_page(page, tag_info, current_url)
						if self._is_not_legit_page(current_url):
							self._get_page_from_dependency(page, current_url)
					else:
						# check if any input is present on the page
						self._check_inputs_on_page(page, tag_info, current_url)
						self.crawl_sess.refresh()
						self._dismiss_alerts()
						self._check_inputs_on_page(page, tag_info, current_url)
				else:
					self.input_space.pop(rand_string)
					if self._is_not_legit_page(current_url):
						self._get_page_from_dependency(page, current_url)

	def _discover_inputs(self, current_url):
		if self._is_not_legit_page(current_url):
			page_dependancies = self._find_page_dependencies(current_url)
		else:
			page_dependancies = [current_url]

		for page in page_dependancies:
			self._check_logged_in(current_url)
			if self._is_not_legit_page(current_url):
				self._get_page_from_dependency(page, current_url)
			initial_source = self.crawl_sess.page_source

			self._check_inputs_on_page(page, current_url=current_url)

			for form_idx in range(len(self.crawl_sess.find_elements_by_xpath('//form'))):
				form_element = self.crawl_sess.find_elements_by_xpath('//form')[form_idx]

				if len(form_element.find_elements_by_xpath('.//input')) > 0:
					input_elements = form_element.find_elements_by_xpath('.//input') + form_element.find_elements_by_xpath('.//textarea')
					input_displays = self.crawl_sess.execute_script("form_nodes=document.evaluate('//form',document,null,XPathResult.ORDERED_NODE_SNAPSHOT_TYPE,null);var display_list=[];for(var i=0;i<form_nodes.snapshotLength;i++){var node_list=[];input_nodes=document.evaluate('.//descendant::input',form_nodes.snapshotItem(i),null,XPathResult.ORDERED_NODE_SNAPSHOT_TYPE,null);text_nodes=document.evaluate('.//descendant::textarea',form_nodes.snapshotItem(i),null,XPathResult.ORDERED_NODE_SNAPSHOT_TYPE,null);for(var j=0;j<input_nodes.snapshotLength;j++){node_list[j]=window.getComputedStyle(input_nodes.snapshotItem(j)).display}for(var x=input_nodes.snapshotLength;x<text_nodes.snapshotLength+input_nodes.snapshotLength;x++){node_list[x]=window.getComputedStyle(text_nodes.snapshotItem(x-input_nodes.snapshotLength)).display}display_list[i]=node_list}return display_list;")
				elif len(form_element.find_elements_by_xpath('./ancestor::div')) > 0:
					input_elements = form_element.find_elements_by_xpath('./ancestor::div')[-1].find_elements_by_xpath('.//descendant::input') + form_element.find_elements_by_xpath('./ancestor::div')[-1].find_elements_by_xpath('.//descendant::textarea')
					input_displays = self.crawl_sess.execute_script("form_nodes=document.evaluate('//form',document,null,XPathResult.ORDERED_NODE_SNAPSHOT_TYPE,null);var display_list=[];for(var i=0;i<form_nodes.snapshotLength;i++){var node_list=[];parents_div_len=document.evaluate('./ancestor::*',form_nodes.snapshotItem(i),null,XPathResult.ORDERED_NODE_SNAPSHOT_TYPE,null).snapshotLength;parent_div=document.evaluate('./ancestor::*',form_nodes.snapshotItem(i),null,XPathResult.ORDERED_NODE_SNAPSHOT_TYPE,null).snapshotItem(parents_div_len-1);input_nodes=document.evaluate('.//descendant::input',parent_div,null,XPathResult.ORDERED_NODE_SNAPSHOT_TYPE,null);text_nodes=document.evaluate('.//descendant::textarea',parent_div,null,XPathResult.ORDERED_NODE_SNAPSHOT_TYPE,null);for(var j=0;j<input_nodes.snapshotLength;j++){node_list[j]=window.getComputedStyle(input_nodes.snapshotItem(j)).display}for(var x=input_nodes.snapshotLength;x<text_nodes.snapshotLength+input_nodes.snapshotLength;x++){node_list[x]=window.getComputedStyle(text_nodes.snapshotItem(x-input_nodes.snapshotLength)).display}display_list[i]=node_list}return display_list;")
				else:
					input_elements = form_element.find_elements_by_xpath('./ancestor::*')[-1].find_elements_by_xpath('.//descendant::input') + form_element.find_elements_by_xpath('./ancestor::*')[-1].find_elements_by_xpath('.//descendant::textarea')
					input_displays = self.crawl_sess.execute_script("form_nodes=document.evaluate('//form',document,null,XPathResult.ORDERED_NODE_SNAPSHOT_TYPE,null);var display_list=[];for(var i=0;i<form_nodes.snapshotLength;i++){var node_list=[];input_nodes=document.evaluate('.//descendant::input',form_nodes.snapshotItem(i),null,XPathResult.ORDERED_NODE_SNAPSHOT_TYPE,null);text_nodes=document.evaluate('.//descendant::textarea',form_nodes.snapshotItem(i),null,XPathResult.ORDERED_NODE_SNAPSHOT_TYPE,null);for(var j=0;j<input_nodes.snapshotLength;j++){node_list[j]=window.getComputedStyle(input_nodes.snapshotItem(j)).display}for(var x=input_nodes.snapshotLength;x<text_nodes.snapshotLength+input_nodes.snapshotLength;x++){node_list[x]=window.getComputedStyle(text_nodes.snapshotItem(x-input_nodes.snapshotLength)).display}display_list[i]=node_list}return display_list;")
				input_display = input_displays[self.crawl_sess.find_elements_by_xpath('//form').index(form_element)]

				submit_all = False

				try:
					re.search('search|query', form_element.get_attribute('action'), re.IGNORECASE)
				except:
					if form_element.get_attribute('action') is None:
						continue

				if re.search('search|query', form_element.get_attribute('action'), re.IGNORECASE) is not None and \
					any(form_element.get_attribute('action') in url for url in self.internal_urls) and \
						any(x != '' for x in self.input_transition_tags[:, self.internal_urls.index(
							[url for url in self.internal_urls if form_element.get_attribute('action') in url][0])]):

					search_url = [url for url in self.internal_urls if form_element.get_attribute('action') in url][0]
					search_idx = self.internal_urls.index(search_url)
					transition_tag =  [i for i in self.tags_that_transition[:,search_idx] if len(i) >= 1][0]
					input_transition_tag = [i for i in self.input_transition_tags[:,search_idx] if len(i) >= 1][0]
					input_transition_tag = {current_url: input_transition_tag[list(input_transition_tag)[0]]}
					self.transition_matrix = self._update_value(self.transition_matrix, 1, current_url, search_url)
					self.input_transitions = self._update_value(self.input_transitions, 1, current_url, search_url)
					self.tags_that_transition = self._update_value(self.tags_that_transition, transition_tag, current_url, search_url)
					self.input_transition_tags = self._update_value(self.input_transition_tags, input_transition_tag, current_url, search_url)
				elif any(input_elements[idx].get_attribute('type') == 'submit' for idx in range(len(input_elements))) or \
						len(form_element.find_elements_by_xpath('.//*[translate(@type,\'ABCDEFGHIJKLMNOPQRSTUVWXYZ\',\'abcdefghijklmnopqrstuvwxyz\') = \'submit\']')) > 0:
					if len(form_element.find_elements_by_xpath('.//*[translate(@type,\'ABCDEFGHIJKLMNOPQRSTUVWXYZ\',\'abcdefghijklmnopqrstuvwxyz\') = \'submit\']')) > 0:
						transition_tag_info = self._get_tag_info(form_element.find_element_by_xpath('.//*[translate(@type,\'ABCDEFGHIJKLMNOPQRSTUVWXYZ\',\'abcdefghijklmnopqrstuvwxyz\') = \'submit\']'))
					else:
						transition_tag_info = self._get_tag_info(
							form_element.find_elements_by_xpath('./ancestor::*')[-1].find_element_by_xpath('.//descendant::*[translate(@type,\'ABCDEFGHIJKLMNOPQRSTUVWXYZ\',\'abcdefghijklmnopqrstuvwxyz\') = \'submit\']'))

					for input_idx in range(len(input_elements)):
						submit_element = None
						for element in input_elements:
							if element.get_attribute('type') == 'submit':
								submit_element = element
						if submit_element is None:
							submit_element = form_element.find_element_by_xpath('.//*[translate(@type,\'ABCDEFGHIJKLMNOPQRSTUVWXYZ\',\'abcdefghijklmnopqrstuvwxyz\') = \'submit\']')

						if submit_element.is_displayed() and submit_element.is_enabled():
							form_element, input_elements, submit_all, rand_string = self._submit_string_to_element(input_elements, input_idx, form_idx,
																									  current_url, submit_element,
																									  submit_all, form_element, page,
																									  initial_source, transition_tag_info, input_displays)

					if submit_all == True:
						try:
							form_element.find_elements_by_xpath('./ancestor::*')[-1].find_element_by_xpath(
								'.//descendant::input[translate(@type,\'ABCDEFGHIJKLMNOPQRSTUVWXYZ\',\'abcdefghijklmnopqrstuvwxyz\') = \'submit\']').get_attribute('name')
						except:
							pass
						if not re.search('login',
										 form_element.find_elements_by_xpath('./ancestor::*')[-1].find_element_by_xpath('.//descendant::*[translate(@type,\'ABCDEFGHIJKLMNOPQRSTUVWXYZ\',\'abcdefghijklmnopqrstuvwxyz\') = \'submit\']').get_attribute('name')
								, re.IGNORECASE) and 'login' not in self.crawl_sess.current_url \
								and (len(form_element.find_elements_by_xpath('./ancestor::*')[-1].find_elements_by_xpath('.//descendant::*[translate(@type,\'ABCDEFGHIJKLMNOPQRSTUVWXYZ\',\'abcdefghijklmnopqrstuvwxyz\') = \'password\']')) == 0 \
									 or re.search('add.user', self.crawl_sess.page_source, re.I)) and submit_all:
							try:
								WebDriverWait(self.crawl_sess, timeout=0.5) \
									.until(EC.element_to_be_clickable((By.XPATH, '//*[@type="submit"]'))).click()
							except:
								ActionChains(self.crawl_sess).move_to_element(self.crawl_sess.find_element_by_xpath(
									'//*[@type="submit"]')).double_click().perform()
								WebDriverWait(self.crawl_sess, timeout=0.5) \
									.until(EC.element_to_be_clickable((By.XPATH, '//*[@type="submit"]'))).click()
						self._check_page_after_input(current_url, transition_tag_info, form_idx, form_element, input_elements, rand_string, page_dependency=page)
				else:

					# put in a random string and see what happens - may need to check the form is not a search bar
					print('no submit button')

					for input_idx in range(len(input_elements)):
							if	input_display[input_idx] != 'none' and \
								input_elements[input_idx].get_attribute('type') != 'file' and \
								input_elements[input_idx].get_attribute('type') != 'hidden':
								transition_tag_info = self._get_tag_info(input_elements[input_idx])
								form_element, input_elements, submit_all , rand_string = self._submit_string_to_element(input_elements, input_idx,
																										  form_idx, current_url, input_elements[input_idx],
																										  submit_all, form_element, page,
																										  initial_source, transition_tag_info, input_displays, True)

					if submit_all == True:
						try:
							if not re.search('login', form_element.find_elements_by_xpath('./ancestor::*')[
								-1].find_element_by_xpath(
								'.//descendant::input[translate(@type,\'ABCDEFGHIJKLMNOPQRSTUVWXYZ\',\'abcdefghijklmnopqrstuvwxyz\') = \'submit\']').get_attribute(
								'name')
									, re.IGNORECASE) and 'login' not in self.crawl_sess.current_url \
									and len(
								form_element.find_elements_by_xpath('./ancestor::*')[-1].find_elements_by_xpath(
									'.//descendant::input[translate(@type,\'ABCDEFGHIJKLMNOPQRSTUVWXYZ\',\'abcdefghijklmnopqrstuvwxyz\') = \'password\']')) == 0 and submit_all:
								try:
									WebDriverWait(self.crawl_sess, timeout=0.5) \
										.until(EC.element_to_be_clickable((By.XPATH, '//*[translate(@type,\'ABCDEFGHIJKLMNOPQRSTUVWXYZ\',\'abcdefghijklmnopqrstuvwxyz\') = \'submit\']'))).click()
								except:
									WebDriverWait(self.crawl_sess, timeout=0.5) \
										.until(EC.element_to_be_clickable((By.XPATH, '//*[translate(@value,\'ABCDEFGHIJKLMNOPQRSTUVWXYZ\',\'abcdefghijklmnopqrstuvwxyz\') = \'submit\']'))).click()
							self._check_page_after_input(current_url, transition_tag_info, form_idx, form_element,
														 input_elements, rand_string, page_dependency=page)
						except:
							print('submit all not found')

