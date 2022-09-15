import requests
import re
from selenium import webdriver
from selenium.common.exceptions import NoAlertPresentException, UnexpectedAlertPresentException, \
	TimeoutException, JavascriptException, NoSuchElementException, WebDriverException
from selenium.webdriver.common.action_chains import ActionChains
import random
import string
from lxml import html
from lxml.html import HtmlComment
import numpy as np
from diff_match_patch.diff_match_patch import *
import difflib
import sys
import pickle
import esprima
import time
import lxml
import os

class Connections:

	def __init__(self, site=[[],[]], difficulty='low', browser='chrome', input_tags = None,
				 injection_form=None, sink=None, input_name=None, transition_tags=None, internal_urls=None,
				 logins=None, login_features=None, headless=True):
		self.browser = browser

		if len(site) == 2:
			if site[0].count('/') > 3:
				self.domain = ''
				for domain_component in site[0].split('/'):
					if self.domain.count('/') < 3:
						self.domain += domain_component + '/'
			else:
				self.domain = site[0]
			self.source = site[1]
			if sink is None:
				self.sink = self.source
			else:
				self.sink = sink
			if transition_tags is not None:
				self.transition_tags = transition_tags
				self.internal_urls   = internal_urls
				self.input_tags 	 = input_tags
				self.logins 	 	 = logins
				self.password        = None
				self.features		 = login_features
				self.current_login 	 = {}
				self.logged_in 		 = False
				self.logout_link 	 = ''
				self.escape 		 = ''
			self.difficulty = difficulty
			self.text_session = self._login()
			self.browser_session = self._instansiate_test_sess(self.browser, headless)
			self._safe_get(site[0], login=False)
			self.filler = None
			self.dom_based = False
			self.source_idx = self.internal_urls.index(self.source)
			self.sink_idx = self.internal_urls.index(self.sink)
			self.to_strip_from_payload = []
			self.actions = []
			self.split=True
			if input_name is None and injection_form != 'URL':
				self.input_names = []
				self.form_method = 'get'
				#self._get_input_space()
			elif injection_form != 'URL':
				self.input_names = {input_name:''}
				self.form_method = self.find_form_method(input_name)
				self.injection_form = input_name
				self.dependency = dict.fromkeys(list(self.input_tags[self.source_idx][self.sink_idx]), {input_name:''})
			else:
				self.form_method = 'get'
				self.source = self.source.split('?')
				inputs = [input.split('=') for input in self.source[1].split('&')]
				self.input_names = {'URL': inputs}
				self.injection_form = inputs[0][0]
				self.source = self.source[0] + '?'
				if '?' in self.sink and 'URL' in self.input_names.keys():
					self.sink = self.sink.split('?')[0]+ '?'
				self.internal_urls[self.source_idx] = self.source
			#self.check_reflection()
			self.context = ''
		else:
			print('Webapp not specified...')

	def save_session_info(self, rank):
		#with open('env/sessions_info_'+rank+'.plk', 'wb') as f:
		dict = {'source': self.source,
				'sink': self.sink,
				'source_idx': self.source_idx,
				'sink_idx': self.sink_idx,
				'injection_form': self.injection_form,
				'input_names': self.input_names,
				'dependency': self.dependency,
				#'text_session': self.text_session,
				'form_method': self.form_method,
				'dom': self.dom_based,
				'current_login': self.current_login,
				'to_strip': self.to_strip_from_payload,
				'internal_urls': self.internal_urls,
				'logins': self.logins,
				'split': self.split,
				'password': self.password,
				'context': self.context}
		with open('sessions_info_'+rank+'.plk', 'wb') as f:
			pickle.dump(dict, f)

	def load_session_info(self, rank):
		#with open('env/sessions_info_'+rank+'.plk','rb') as f:
		with open('sessions_info_'+rank+'.plk','rb') as f:
			dict = pickle.load(f)
			self.source = dict['source']
			self.sink = dict['sink']
			self.source_idx = dict['source_idx']
			self.sink_idx = dict['sink_idx']
			self.injection_form = dict['injection_form']
			self.input_names = dict['input_names']
			self.dependency = dict['dependency']
			self.form_method = dict['form_method']
			self.dom_based = dict['dom']
			self.split = dict['split']
			self.current_login = dict['current_login']
			self.to_strip_from_payload = dict['to_strip']
			self.internal_urls = dict['internal_urls']
			self.logins = dict['logins']
			self.password = dict['password']
			self.context = dict['context']




	def close(self):
		self.text_session.close()
		self.browser_session.quit()


	def _instansiate_test_sess(self, browser, headless):
		if browser == 'chrome':
			options = webdriver.ChromeOptions()
			if headless:
				#pass
				options.add_argument('--headless')
				options.add_argument('--no-sandbox')
				options.add_argument('--disable-gpu')
				options.add_argument('--disable-dev-shm-usage')
				options.add_argument('--window-size=1920, 1080')
			driver = webdriver.Chrome(options=options)
		elif browser == 'firefox':
			options = webdriver.FirefoxOptions()
			if headless:
				options.add_argument('-headless')
			driver = webdriver.Firefox(options=options)
		driver.get(self.domain)
		for cookie in self.text_session.cookies:
			key = str(cookie).split('=')[0].split(' ')[1]
			value = str(cookie).split('=')[1].split(' ')[0]
			driver.add_cookie({'name':key, 'value':value})
		return driver


	def create_cleanup_string(self, escape_string):
		cleanup_string = ''
		for char in escape_string:
			if char == '"':
				cleanup_string = '"' + cleanup_string
			if char == "'":
				cleanup_string = "'" + cleanup_string
			if char == ';':
				cleanup_string = ";" + cleanup_string
			if char ==')':
				cleanup_string = '(' + cleanup_string
			if char =='}':
				cleanup_string = '{' + cleanup_string
			if char ==']':
				cleanup_string = '[' + cleanup_string
			if char =='>':
				cleanup_string = '<' + cleanup_string
			if char =='-':
				cleanup_string = '-' + cleanup_string
		first_single_quote = len(cleanup_string.split("'")[0])
		first_double_quote = len(cleanup_string.split('"')[0])
		if first_single_quote < first_double_quote and first_single_quote != len(cleanup_string):
			cleanup_string = cleanup_string[:first_single_quote]+'a='+ cleanup_string[first_single_quote:]
		elif first_single_quote > first_double_quote and first_double_quote != len(cleanup_string):
			cleanup_string = cleanup_string[:first_double_quote]+'a='+ cleanup_string[first_double_quote:]
		return cleanup_string

	def get_all_names_of_form(self, page):
		element_info = self.input_tags[self.source_idx][self.sink_idx][page]
		element_name = ['name', element_info['name']] if element_info['name'] != '' else ['value',
																						  element_info['value']]
		element_name.append(element_info['tag_name'])
		self.browser_session.get(self.source)
		target_element = self.browser_session.find_element_by_xpath('//'+element_name[2]+'[@'+element_name[0]+'="'+element_name[1]+'"]')
		#	find_element_by_name(element_name)
		if len(target_element.find_elements_by_xpath('./ancestor::form')) > 0:
			input_elements = target_element.find_element_by_xpath('./ancestor::form').find_elements_by_xpath(
				'.//descendant::input') + target_element.find_element_by_xpath('./ancestor::form').find_elements_by_xpath('.//descendant::textarea')
			self.input_names = {element.get_attribute('name'): element.get_attribute('value') for element in input_elements if element.get_attribute('name') != ''}
			return  self.browser_session.find_element_by_name(list(self.input_names)[0]).find_elements_by_xpath('./ancestor::form')[-1].get_attribute('action')
		elif len(target_element.find_elements_by_xpath('./ancestor::div')[-1].find_elements_by_xpath('.//descendant::form')) > 0:
			input_elements = target_element.find_elements_by_xpath('./ancestor::div')[-1].find_elements_by_xpath(
				'.//descendant::input') + target_element.find_element_by_xpath('./ancestor::div').find_elements_by_xpath('.//descendant::textarea')
			self.input_names = {element.get_attribute('name'): element.get_attribute('value') for element in input_elements if element.get_attribute('name') != ''}
			return  self.browser_session.find_element_by_name(list(self.input_names)[0]).find_elements_by_xpath('./ancestor::div')[-1].find_element_by_xpath('.//form').get_attribute('action')


	def find_form_method(self, injection_form):
		fuzz_source = self.text_session.get(self.source)
		page_source = fuzz_source.text
		if fuzz_source.status_code == 404:
			page_to_source = [self.internal_urls[i] for i in range(self.transition_tags.shape[0]) if self.transition_tags[i, self.source_idx] != '' ][0]
			tag_info = self.transition_tags[self.internal_urls.index(page_to_source)][self.source_idx]
			while fuzz_source.status_code == 404 and self.browser_session.current_url.split('?')[0]+'?' != self.source \
					and self.browser_session.current_url != self.source:
				self._safe_get(page_to_source)
				try:
					self.browser_session.find_element_by_xpath('//input[@value="'+tag_info['value']+'"]').click()
				except:
					try:
						self._safe_get(self.source)
						tag_info = self.transition_tags[self.source_idx][self.sink_idx]
						try:
							self.browser_session.find_element_by_xpath('//input[@value="' + tag_info['value'] + '"]').click()
						except:
							self._safe_get(page_to_source)
							tag_info = self.transition_tags[self.internal_urls.index(page_to_source)][self.source_idx]
							self.browser_session.find_element_by_xpath('//*[text() = "' + tag_info['tag_text'] + '"]').click()
					except:
						if self.source in [self.internal_urls[i] for i in range(self.transition_tags.shape[0]) if self.transition_tags[i, self.source_idx] != '']:
							self._safe_get(self.source)
							self.browser_session.find_element_by_xpath('//input[@value="' + tag_info['value'] + '"]').click()
						else:
							found = False
							page_to_source = [self.internal_urls[i] for i in range(self.transition_tags.shape[0]) if
											  self.transition_tags[i, self.source_idx] != '']
							page_idx = 0
							while found == False:
								try:
									self._safe_get(page_to_source[page_idx])
									tag_info = self.transition_tags[self.internal_urls.index(page_to_source[page_idx])][
										self.source_idx]
									self.browser_session.find_element_by_xpath(
										'//input[@value="' + tag_info['value'] + '"]').click()
									found = True
									page_to_source = page_to_source[page_idx]
								except:
									page_idx += 1
				url = self.browser_session.current_url if '?' not in self.browser_session.current_url else self.browser_session.current_url.split('?')[0] + '?'
				tag_info = self.transition_tags[self.internal_urls.index(url)][
					self.internal_urls.index(page_to_source)]
				page_to_source = [self.internal_urls[i] for i in range(self.transition_tags.shape[0]) if
								  self.transition_tags[i, self.source_idx] != ''][0]
				page_source = self.browser_session.page_source
		if 'URL' in self.input_names:
			return 'get'
		else:
			page_split = re.split('name=(\'|")'+injection_form, page_source)[0]
			form_method = re.findall('form.*method=(\'|")(\w*)(\'|")', page_split, re.IGNORECASE)
			if len(form_method) > 0:
				form_method = form_method[-1][1]
				if re.match('post', form_method, re.IGNORECASE):
					return 'post'
				elif re.match('get', form_method, re.IGNORECASE):
					return 'get'
				return re.findall('form.*method=(\'|")(\w*)(\'|") ', page_split)[-1][1]
			else:
				return 'get'

	# function to determine the order of chars in a string
	def _order_vals(self, unordered_list, matching_string):
		loc_dict = {}
		for item in unordered_list:
			item_location = matching_string.find(item)
			loc_dict[item] = item_location
		ordered_list = {k: v for k, v in sorted(loc_dict.items(), key=lambda item: item[1], reverse=True)}
		return ordered_list

	def _find_page_dependancies(self, url):
		return  [self.internal_urls[i] for i in range(self.transition_tags.shape[0]) if self.transition_tags[i, self.internal_urls.index(url)] != '']

	def _get_dependency_info(self, target, input_dependencies):
		for input_dependency in input_dependencies:
			if self.transition_tags[self.internal_urls.index(input_dependency)][self.internal_urls.index(target)] != '':
				if self.features[self.internal_urls.index(input_dependency)][0] != 0:
					self.login(list(self.current_login)[0], self.current_login[(list(self.current_login)[0])])
				dependency_response = self.text_session.get(input_dependency)
				if 'HTTP ERROR' in dependency_response.text or dependency_response.status_code != 200:
					self._get_dependency_info(input_dependency, self._find_page_dependancies(input_dependency))
					if self.form_method == 'post':
						dependency_response = self.text_session.post(input_dependency, data=self.dependency[input_dependency])
					elif self.form_method == 'get':
						dependency_response = self.text_session.get(input_dependency, params=self.dependency[input_dependency])
				if self.features[self.internal_urls.index(input_dependency)][0] != 0:
					self.logout()
				input_tag = self.transition_tags[self.internal_urls.index(input_dependency)][self.internal_urls.index(target)]
				input_elements = ['name', input_tag['name']] if input_tag['name'] != '' else ['value',input_tag['value']]
				input_elements.append(input_tag['tag_name'])


				dependency_tree = lxml.html.fromstring(dependency_response.text)

				action, payload = self._retrive_action_payload_from_html_tree(dependency_tree, input_elements)
				action = self.domain[:-1] + action if action[0] == '/' else self.domain + action
				self.dependency[action] = payload

				self._send_payload('some_string')

	def _retrive_action_payload_from_html_tree(self, payload_tree, input_info):
		if len(payload_tree.xpath(
				'//' + input_info[2] + '[@' + input_info[0] + '="' + input_info[1] + '"]//ancestor::form')) > 0:
			input_elements = payload_tree.xpath('//' + input_info[2] + '[@' + input_info[0] + '="' + input_info[1] + '"]//ancestor::form[//'+input_info[2]+'[@'+input_info[0]+'="'+input_info[1]+'"]]//input')
			textarea_elements = payload_tree.xpath('//' + input_info[2] + '[@' + input_info[0] + '="' + input_info[1] + '"]//ancestor::form[//'+input_info[2]+'[@'+input_info[0]+'="'+input_info[1]+'"]]//textarea')
			option_elements = payload_tree.xpath('//' + input_info[2] + '[@' + input_info[0] + '="' + input_info[1] + '"]//ancestor::form[//'+input_info[2]+'[@'+input_info[0]+'="'+input_info[1]+'"]]//select//option[@selected="selected"]')
			select_elements = payload_tree.xpath('//' + input_info[2] + '[@' + input_info[0] + '="' + input_info[1] + '"]//ancestor::form[//'+input_info[2]+'[@'+input_info[0]+'="'+input_info[1]+'"]]//select')
			action = payload_tree.xpath(
				'//' + input_info[2] + '[@' + input_info[0] + '="' + input_info[1] + '"]//ancestor::form')[0].action
			payload = {element.name: element.value for element in input_elements if
					   element.type not in 'file' and element.name != '' and element.name is not None and element.value is not None}
			if payload == {} and len(input_elements) != 0:
				payload = {element.name: element.value for element in input_elements if
				 		element.type not in 'file' and element.name != '' and element.name is not None}
			payload.update({element.name: element.value for element in textarea_elements if
							element.name != '' and element.name is not None})
			payload.update({select_elements[idx].name: option_elements[idx].attrib['value'] for idx in range(len(option_elements)) if
							select_elements[idx].name != '' and select_elements[idx].name is not None})
		else:
			input_elements = payload_tree.xpath('//' + input_info[2] + '[@' + input_info[0] + '="' + input_info[1] + '"]//ancestor::*[//'+input_info[2]+'[@'+input_info[0]+'="'+input_info[1]+'"]]//input')
			textarea_elements = payload_tree.xpath('//' + input_info[2] + '[@' + input_info[0] + '="' + input_info[1] + '"]//ancestor::*[//'+input_info[2]+'[@'+input_info[0]+'="'+input_info[1]+'"]]//textarea')
			option_elements = payload_tree.xpath(
				'//' + input_info[2] + '[@' + input_info[0] + '="' + input_info[1] + '"]//ancestor::*[//' +
				input_info[2] + '[@' + input_info[0] + '="' + input_info[
					1] + '"]]//select//option[@selected="selected"]')
			select_elements = payload_tree.xpath(
				'//' + input_info[2] + '[@' + input_info[0] + '="' + input_info[1] + '"]//ancestor::*[//' +
				input_info[2] + '[@' + input_info[0] + '="' + input_info[1] + '"]]//select')

			actions = payload_tree.xpath(
				'//' + input_info[2] + '[@' + input_info[0] + '="' + input_info[1] + '"]//ancestor::*//form['+input_info[2]+'[@'+input_info[0]+'="'+input_info[1]+'"]]')
			if len(actions) > 0:
				action = actions[0].action
				payload = {element.name: element.value for element in input_elements if
						   element.type not in 'file' and element.name != '' and element.name is not None and element.value is not None}
				payload.update({element.name: element.value for element in textarea_elements if
								element.name != '' and element.name is not None})
				payload.update({select_elements[idx].name: option_elements[idx].attrib['value'] for idx in
								range(len(option_elements)) if select_elements[idx].name != '' and select_elements[idx].name is not None})
			else:
				# there are no actions on the page
				# in this case there is no dependency, it is the final page
				# there for return the current inputs
				action = None
				payload = self.input_names
		self.actions.append(action)
		#if action is not None and '..' in action:
		#	action = action.split('../')[-1]
		return action, payload

	def _get_dependant_form_info(self, url, page_response, update_filler=False, source_idx=None, sink_idx=None):
		if source_idx == None:
			source_idx = self.source_idx
		if sink_idx == None:
			sink_idx = self.sink_idx
		inputs_ = self.input_tags[source_idx][sink_idx]
		if self.features[source_idx][0] != 0 and not self.logged_in:
			source_login = self.features[source_idx][0]
			login_details = self.logins[list(self.logins)[source_login - 1]]
			self.login(list(self.logins)[source_login - 1], login_details)
			if len(self.dependency) == 1:
				page_response = self.text_session.get(self.source).content
		if url in inputs_.keys():
			if len(page_response) > 0:
				payload_tree = html.fromstring(page_response)
			else:
				payload_tree = html.fromstring(self.text_session.get(url).content)
			input_ = [inputs_[url][i] for i in range(len(inputs_[url])) if list(self.input_names)[0] in inputs_[url][i].values()]
			if not input_:
				input_ = inputs_[url][0]
			else:
				input_ = input_[0]
		else:
			url = self.source
			payload_tree = html.fromstring(self.text_session.get(self.source).content)
			if any(self.source in input_url for input_url in inputs_.keys()):
				for input_url in inputs_.keys():
					if self.source in input_url:
						source_url = input_url
						break
			else:
				source_url = self.source

			input_ = [inputs_[source_url][i] for i in range(len(inputs_[source_url])) if list(self.input_names)[0] in inputs_[source_url][i].values()]
			if not input_:
				input_ = inputs_[source_url][0]
			else:
				input_ = input_[0]
		input_info = ['name', input_['name']] if input_['name'] != '' else ['value',input_['value']]
		input_info.append(input_['tag_name'])
		action, payload = self._retrive_action_payload_from_html_tree(payload_tree, input_info)
		filler =  ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(6))
		if update_filler == True:
			self.filler = filler
		#password_keys = []
		for key in payload:
			if key != self.injection_form and not payload[key]:
				if re.search('email', key, re.IGNORECASE) is not None:
					payload[key] = filler + '@email.com'
				elif re.search('password', key, re.IGNORECASE) is not None or ('type' in payload_tree.xpath('//*[@name="' + key + '"]')[0].attrib and payload_tree.xpath('//*[@name="'+key+'"]')[0].type == 'password'):
					if len(list(self.current_login)) != 0:
						payload[key] = self.current_login[list(self.current_login)[0]][1]
					else:
						payload[key] = filler
					if update_filler:
						self.password = payload[key]
					if re.search('signup|sign_up|register', self.source, re.IGNORECASE) is None:
					 	self.current_login[list(self.current_login)[0]][1] = self.password
					#password_keys.append(key)
				else:
					payload[key] = filler
		#	payload.pop(key)
		if not action:
			action = self.source
		else:
			new_action = ''
			for url_part in url.split('/')[:-1]:
				if url_part not in action.split('/') or url_part == '':
					new_action += url_part + '/'
				#new_action += url_part + '/'
			#action = url +'/' +action if action[0] != '/' else url + action[1:]
			if new_action not in action:
				if new_action[-1] != '/' and action[0] != '/' :
					possible_action = new_action + action[1:]
				elif new_action[-1] != '/' or action[0] != '/' :
					possible_action = new_action + action
				else:
					possible_action = new_action + '/' + action
				#possible_action = new_action + action if new_action[-1] != '/' and action[0] != '/' else  new_action + action[1:]

			if self.text_session.get(possible_action).status_code == 404:
				 action = self.domain + action
			else:
				action = possible_action
		return action, payload

	def _add_dependency(self, new_url, prev_url_idx):
		if new_url not in self.dependency:
			dependency_list = list(self.dependency)
			try:
				prev_dep_idx = dependency_list.index(self.internal_urls[prev_url_idx])
				dependency_list.insert(prev_dep_idx, new_url)
				self.dependency[new_url] = {}
				self.dependency = {dependency: self.dependency[dependency] for dependency in dependency_list}
			except:
				dependency_list.insert(0, new_url)
				self.dependency[new_url] = {}
				self.dependency = {dependency: self.dependency[dependency] for dependency in dependency_list}

	def _find_page_links(self, rand_string, url_idx):
		try:
			transition_tags = self.transition_tags[:, url_idx]
		except:
			print('error finding page link...')
		urls_to_transition = [self.internal_urls[i] for i in range(self.transition_tags.shape[0]) if
							  self.transition_tags[i, url_idx] != '']
		form_action = 'non_value'
		for idx in range(len(urls_to_transition)):
			form_action = urls_to_transition[idx]
			if self.features[self.internal_urls.index(form_action)][0] != 0 and not self.logged_in:
				source_login = self.features[self.internal_urls.index(form_action)][0]
				login_details = self.logins[list(self.logins)[source_login - 1]]
				self.login(list(self.logins)[source_login - 1], login_details)
			if self.text_session.get(form_action).status_code != 200:
				rand_string_found = self._find_page_links(rand_string, self.internal_urls.index(form_action))
				if rand_string_found[0] == True:
					self._add_dependency(form_action, url_idx)
					return True, rand_string_found[1]
				else:
					continue
			page_response = self.text_session.get(form_action)
			if rand_string in str(page_response) and page_response.url == self.sink:
				self._add_dependency(form_action, url_idx)
				return True, page_response
			payload_tree = html.fromstring(page_response.content)
			input_ = transition_tags[self.internal_urls.index(form_action)]
			input_info = ['name', input_['name']] if input_['name'] != '' else ['value', input_['value']]
			input_info.append(input_['tag_name'])
			if all(len(input) > 0 for input in input_info):
				action, payload = self._retrive_action_payload_from_html_tree(payload_tree, input_info)
				if action is not None:
					action = self.domain[:-1] + action if action[0] == '/' else self.domain + action
				if action is not None:
					self.dependency[action] = payload
					_, url_returned,payload_returned = self._send_payload(rand_string, action)
					new_action, new_payload = self._get_dependant_form_info(url_returned, payload_returned.text)
					self.dependency[new_action] = new_payload
					payload_returned, payload_context = self.send_payload(rand_string)
					if rand_string in payload_returned:
						self._add_dependency(form_action, url_idx)
						return True, payload_context
				if action != self.sink and action is not None and action in self.internal_urls and self.internal_urls.index(action) != url_idx:
					self._add_dependency(form_action, url_idx)
					self.dependency.pop(action)
					rand_string_found = self._find_page_links(rand_string, self.internal_urls.index(action))
					if rand_string_found[0] == True:
						return True, rand_string_found[1]
				if action is not None and action in self.dependency:
					self.dependency.pop(action)
		if form_action in self.dependency:
			self.dependency.pop(form_action)
		if form_action == 'non_value':
			return False, ''
		else:
			return False, page_response


	def check_reflection(self):
		self.split = True
		if 'URL' in self.input_names.keys():
			self.dependency = dict.fromkeys(list(self.input_tags[self.source_idx][self.sink_idx]), {self.source:self.input_names['URL']})
			keys = list(self.dependency.keys())
			for key in keys:
				if self.source in key and self.source != key:
					self.dependency[self.source] = self.dependency[key]
					self.dependency.pop(key)
		else:
			self.dependency = dict.fromkeys(list(self.input_tags[self.source_idx][self.sink_idx]), self.input_names)
		self.actions = [self.source]
		for input in self.input_names.keys():
			rand_string = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(6))
			blank_request, url_returned, payload_response = self._send_payload(rand_string)
			# if the sink is not current page, get current sink as stored xss
			if self.sink.split('?')[0] not in url_returned and blank_request.status_code != 404:
				payload_response = self.text_session.get(self.sink)

			returned_string = ''.join([li for li in difflib.ndiff(payload_response.text.splitlines(), blank_request.text.splitlines()) if li[0] not in ' ?+'])
			if re.search(rand_string, returned_string, re.I):
				self.to_strip_from_payload = returned_string.split(rand_string)
				if 'URL' in self.input_names.keys():
					self.dependency[self.sink] = self.dependency.pop(self.internal_urls[self.source_idx])
				elif self.source in self.dependency:
					self.dependency[self.sink] = self.dependency.pop(self.source)
				else:
					dependencies = self.dependency.keys()
					for key in dependencies:
						if self.source in key:
							self.dependency[self.sink] = self.dependency.pop(key)
							break

				self.dom_based = False
				return self.get_escape_string(payload_response.text, rand_string)
			else:
				payload_found = False
				blank_request, url_returned, payload_response = self._send_payload(rand_string)
				count = 0
				while payload_found == False and count < 5:
					count += 1
					form_action, payload = self._get_dependant_form_info(payload_response.url, payload_response.content, update_filler=True)


					self.dependency[form_action] = payload
					self.input_names = payload
					if count > 4:
						payload_found, payload_response = self._find_page_links(rand_string, self.sink_idx)
						if type(payload_found) != bool:
							payload_found = False
						if payload_found == True:
							self.dom_based = False
							self.to_strip_from_payload = returned_string.split(rand_string)

							return self.get_escape_string(payload_response, rand_string)
						self.split = False
						#blank_request, url_returned, payload_response = self._send_payload(rand_string, form_action,
						#																		   split)

					blank_request, url_returned, payload_response = self._send_payload(rand_string, form_action)


					if self.features[self.source_idx][0] != 0 and rand_string not in payload_response.text :
						if self.sink.split('?')[0] not in url_returned and blank_request.status_code != 404:
							payload_response = self.text_session.get(self.sink)
						self.logout()

					if re.search('signup|register', self.source) or  self.features[self.source_idx][0] != 0\
							and rand_string not in payload_response.text:

						login_acc = self.current_login[list(self.current_login)[0]]
						for usr_login in self.logins.keys():
							if re.search('signup|register', self.source) and self.password is not None:
								login_acc = [self.logins[usr_login][0], self.password]
								usr_login = rand_string if re.search('username', self.injection_form, re.IGNORECASE) else self.filler
							self.login(usr_login, login_acc)
							payload_response = self.text_session.get(self.sink)
							self.logout()
							if rand_string in payload_response.text:
								break
					if (self.features[self.source_idx][0] != 0 or \
							self.features[self.sink_idx][0] != 0) and \
							rand_string not in payload_response.text:
						sink_login = self.features[self.sink_idx][0]
						source_login = self.features[self.source_idx][0]
						login_idx = sink_login if sink_login > source_login else source_login
						login_details = self.logins[list(self.logins)[login_idx - 1]]
						self.login(list(self.logins)[login_idx - 1], login_details)
						payload_response = self.text_session.get(self.sink)
						self.logout()
						#blank_request, url_returned, payload_response = self._send_payload(rand_string, form_action)

					#if self.sink not in url_returned and blank_request.status_code != 404:
					#	payload_response = self.text_session.get(self.sink)
					returned_string =''.join([li for li in difflib.ndiff(payload_response.text.splitlines(), blank_request.text.splitlines()) if li[0] not in ' ?+'])

					if re.search(rand_string, returned_string, re.I) and (payload_response.url == self.sink or payload_response.url.replace(rand_string, '') == self.sink) or re.search(rand_string, self.text_session.get(self.sink).text, re.I):
						self.to_strip_from_payload = returned_string.split(rand_string)
						self.input_names = self.dependency[self.source]
						self.dependency[form_action] = payload
						payload_found = True
						self.dom_based = False
						return self.get_escape_string(payload_response.text, rand_string)
					elif url_returned != self.sink:
						print('Could not interact with form correctly: Attempting to find dependency')
						print(self.source)
						print(self.sink)
					else:
						print('Could not interact with form correctly: No payload detected')
						print(self.input_names)
						print(self.source)
						print(self.sink)
				print("Checking for potential DOM XSS")
				escapes = self.check_dom_xss(rand_string)
				if escapes is not None:
					print('DOM payload found')
					self.dom_based = True
					return escapes
				else:
					self.dom_based = False
					return  None, None

	def get_js_token(self, node, token):
		node_type = node.type
		if 'BlockStatement' in node_type:
			return '}'
		elif 'ExpressionStatement' in node_type:
			if node.expression.type == 'CallExpression':
				for argument in node.expression.arguments:
					if argument.raw and token in argument.raw:
						escape = argument.raw.split(token)[-1]
				return escape + ');'
			elif node.expression.type == 'ClassExpression':
				return '}'
			elif node.expression.type == 'AssignmentExpression':
				if token in node.expression.right.raw:
					return node.expression.right.raw.split(token)[-1]
				else:
					return node.expression.left.raw.split(token)[-1]
			else:
				if node.expression.raw:
					return node.expression.raw.split(token)[-1]
				elif node.expression.name:
					return node.expression.name.split(token)[-1]
				else:
					return ''
		elif 'VariableDeclaration' in node_type:
			if node.declarations[0].init.type == 'ArrayExpression':
				for element in node.declarations[0].init.elements:
					if token in element.raw:
						escape = element.raw.split(token)[-1]
						return escape + '];'
				return '];'
			elif node.declarations[0].init.type == 'Literal':
				if token in node.declarations[0].init.raw:
					escape = node.declarations[0].init.raw.split(token)[-1]
					return escape + ';'
				elif token in node.declarations[0].id.name:
					escape = node.declarations[0].id.name.split(token)[-1]
					return ';'
			elif node.declarations[0].init.type == 'ObjectExpression':
				for object in node.declarations[0].init.properties:
					if object.key.raw and token in object.key.raw:
						escape = object.key.raw.split(token)[-1]
						return escape + ':\'val\'};'
					elif object.value.raw and token in object.value.raw:
						escape = object.value.raw.split(token)[-1]
						return escape + '};'

	def get_js_escape(self, js_tree, token, escape_string, update_escape=True):
		if js_tree.comments is not None and len(js_tree.comments) > 0:
			comment_escape = None
			for comment in js_tree.comments:
				if token in comment.value:
					if comment.type == 'Block':
						comment_escape = {'start': comment.loc.start, 'end': comment.loc.end, 'escape': '*/'}
					elif comment.type == 'Line':
						comment_escape = {'start': comment.loc.start, 'end': comment.loc.end, 'escape': '%0D%0A'}
		else:
			comment_escape = None
		if js_tree.body is not None:
			js_tree = js_tree.body
		for node in js_tree:
			if node.type == 'FunctionDeclaration':
				node = node.body
			if comment_escape is not None:
				if node.loc.start.line <= comment_escape['start'].line and node.loc.end.line >= comment_escape[
					'end'].line \
						and node.loc.start.column <= comment_escape['start'].column and node.loc.end.column >= \
						comment_escape['end'].column:
					escape_string = comment_escape['escape'] + self.get_js_token(node, token)
			if token in str(node):
				if node.body is None:
					escape_string = self.get_js_token(node, token) + escape_string
					if update_escape:
						self.escape = escape_string
					return escape_string
				escape_string = self.get_js_token(node, token) + escape_string
				escape_string = self.get_js_escape(node, token, escape_string)
			# get the child nodes from the string and make the escape string
		if comment_escape is not None and escape_string == '':
			escape_string = comment_escape['escape']
		if update_escape == True:
			self.escape = escape_string
		return escape_string

	def get_escape_string(self, page_response, test_payload, get_context=False):
		page_tree = html.fromstring(page_response)
		# find test_payload in a tag text
		target_xpath = page_tree.xpath('//*[contains(.,"' + test_payload + '")]')
		# find the test_payload in the attribute of a tag
		if len(target_xpath) == 0:
			target_xpath = page_tree.xpath('//*[@*[contains(.,"' + test_payload + '")]]')
		if len(target_xpath) == 0: # check inside a comment
			target_xpath = page_tree.xpath('//comment()[contains(.,"' + test_payload + '")]')
		if len(target_xpath) > 0:
			target_tag = target_xpath[-1]
			text = target_tag.text
			if text is None or test_payload not in text:
				xpath_to_node = page_tree.getroottree().getpath(target_xpath[-1])
				text = ' '.join(str(text) for text in page_tree.xpath(xpath_to_node + '/text()'))

			if type(target_tag) == HtmlComment:
				escape_string = '-->'
				escape_tag = ''
				if not get_context:
					self.context = 'comment'
				else:
					return 'comment'
			elif target_tag.tag == 'script' and test_payload in text:
				try:
					escape_string = self.get_js_escape(
						esprima.parseScript(target_tag.text, options={'comment': True, 'loc': True}), test_payload, '')
				except:
					# if there is an error in parsing the JS then be exhaustive in making
					# the escape string
					post_payload = target_tag.text.split(test_payload)[-1]
					escape_locs = {}
					if post_payload.count('"') % 2 != 0:
						escape_locs['"'] = post_payload.find('"')
					if post_payload.count('\'') % 2 != 0:
							escape_locs['\''] = post_payload.find('\'')
					if post_payload.count('{') != post_payload.count('}'):
						escape_locs['}'] = post_payload.find('}')
					if post_payload.count('(') != post_payload.count(')'):
						escape_locs[')'] = post_payload.find(')')
					if post_payload.count('/*') != post_payload.count('*\\'):
						escape_locs['*/'] = post_payload.find('*/')
					escape_string = ''.join(sorted(escape_locs.keys(), key=lambda x:x))
				escape_tag = target_tag.tag
				if not get_context:
					self.context = 'javascript'
				else:
					return 'javascript'
			elif text is not None and test_payload in text:
				escape_string = '"' if '"' in text.split(test_payload)[0] else ''
				escape_string = "'" if "'" in text.split(test_payload)[0] else escape_string
				if '"' in escape_string and "'" in escape_string:
					if target_tag.text.rfind('"') < text.rfind("'"):
						escape_string = '\'"'
					else:
						escape_string = '"\''
				if page_response.split(test_payload)[0].count(")") != page_response.split(test_payload)[
					0].count("("):
					escape_string = escape_string[:-1] + ')' + escape_string[-1:]
				if page_response.split(test_payload)[0].count("}") != page_response.split(test_payload)[
					0].count("{"):
					escape_string += '}'

				escape_tag = target_tag.tag
				if not get_context:
					self.context = 'tag'
				else:
					return 'tag'
			elif any(test_payload in attribute_val for attribute_val in target_tag.attrib.values()):
				try:
					for attr_val in target_tag.attrib.values():
						if test_payload in attr_val:
							attr_script = attr_val
					escape_string = self.get_js_escape(
						esprima.parseScript(attr_script, options={'comment': True, 'loc': True}), test_payload, '')
					escape_string += '"' if page_response.split(test_payload)[0].count('"') % 2 != 0 else "'"
				except:
					escape_string = '"' if page_response.split(test_payload)[0].count('"') % 2 != 0 else ''
					escape_string = "'" + escape_string if page_response.split(test_payload)[0].count(
						"'") % 2 != 0 else escape_string
					if '"' in escape_string and "'" in escape_string:
						if page_response.split(test_payload)[0].rfind('"') < \
								page_response.split(test_payload)[0].rfind("'"):
							escape_string = '\'"'
						else:
							escape_string = '"\''
					if page_response.split(test_payload)[0].count(")") != page_response.split(test_payload)[
						0].count("("):
						escape_string = escape_string[:-1] + ')' + escape_string[-1:]
				escape_tag = target_tag.tag
				if not get_context:
					self.context = 'attribute'
				else:
					return 'attribute'
			else:
				escape_string, escape_tag = ' ', ' '
		else:
			escape_string, escape_tag = ' ', ' '
		try:
			return escape_string, escape_tag
		except:
			pass

	def check_context_change(self, page, current_tag, token):
		if token not in page:
			return None
		page_tree = lxml.html.fromstring(page)
		if self.context == 'comment':
			target_xpath = page_tree.xpath('//comment()[contains(.,"'+token+'")]')
		elif self.context == 'attribute':
			target_xpath = page_tree.xpath('//*[@*[contains(.,"' + token + '")]]')
		elif self.context == 'tag':
			target_xpath = page_tree.xpath('//*[contains(.,"'+token+'")]')
			if len(target_xpath) > 0 and target_xpath[-1].tag != current_tag:
				target_xpath = []
			else:
				target_xpath = ['no context change']
		elif self.context == 'javascript':
			target_xpath = page_tree.xpath('//*[contains(.,"' + token + '")]')
			if len(target_xpath) > 0 and target_xpath[-1].tag != current_tag:
				target_xpath = []
			else:
				try:
					payload_returned = target_xpath[-1].text
					if payload_returned.count(')') > payload_returned.count('('):
						split_by_payload = payload_returned.split(token)
						l_payload = split_by_payload[0]
						r_payload = split_by_payload[-1]
						r_payload = r_payload.replace(')', '', 1)
						payload_returned = l_payload +token.join(split_by_payload[1:-1]) + token + r_payload
					if payload_returned.count('}') > payload_returned.count('{'):
						split_by_payload = payload_returned.split(token)
						l_payload = split_by_payload[0]
						r_payload = split_by_payload[-1]
						r_payload = r_payload.replace('}', '', 1)
						payload_returned = l_payload +token.join(split_by_payload[1:-1]) + token + r_payload
					prev_escape = self.escape
				except:
					pass
				try:
					if self.get_js_escape(
							esprima.parseScript(payload_returned, options={'comment': True, 'loc': True, 'tolerant': True}),
							token, '', update_escape=False)[-len(prev_escape):]  == prev_escape:
						target_xpath = ['no context change']
					else:
						target_xpath = []
				except:
					# if this breaks then we consider the context to have changed
					target_xpath = []
		if len(target_xpath) > 0:
			return None
		else:
			return self.get_escape_string(page, token, get_context=True)

	def _get_input_space(self):
		try:
			self.browser_session.get(self.source)
			inputs = self.browser_session.find_elements_by_tag_name('input')
			for input in inputs:
				if input.get_attribute('name'):
					self.input_names.append(input.get_attribute('name'))
		except:
			print('Error in identifying inputs to test...')
			print('Exiting from connect.py "_get_input_space"...')
			print(sys.exc_info()[0])
			self.close()
			exit()


	def _attempt_accept_payload(self, token='I am never going to be in the payload'):
		no_payloads = False
		malicious_payload = False
		while no_payloads == False:
			try:
				time.sleep(0.2)
				if token.strip('0') in self.browser_session.switch_to.alert.text:
					self.browser_session.switch_to.alert.accept()
					malicious_payload = True
				self.browser_session.switch_to.alert.accept()
			except NoAlertPresentException:
				no_payloads = True
		return malicious_payload



	def _check_alert_on_page(self, events, token, ttl):
		try:
			for event in events:
				if re.search('key', event, re.IGNORECASE):
					time.sleep(0.025)
					self.browser_session.execute_script('var keyboardEvent = new KeyboardEvent("keypress"); document.body.dispatchEvent(keyboardEvent);')
					ActionChains(self.browser_session).click(self.browser_session.find_element_by_name(list(self.input_names)[0])).perform()
					try:
						self.browser_session.find_element_by_name(list(self.input_names)[0]).send_keys('w')
					except:
						pass
					try:
						output_element = self.browser_session.find_elements_by_xpath('//*[@onkeypress="alert('+token+')"]')[0]
						ActionChains(self.browser_session).click(output_element).perform()
						output_element.send_keys('q')
					except:
						pass
				if re.search('mouse', event, re.IGNORECASE):
					time.sleep(0.025)
					self.browser_session.execute_script('var event = document.createEvent( "Events" );event.initEvent( "' + event[2:] + '", true, false );document.getElementsByName("' + list(self.input_names)[0] + '")[0].dispatchEvent(event);')
					time.sleep(0.03)
					ActionChains(self.browser_session).click(self.browser_session.find_element_by_name(list(self.input_names)[0])).perform()
					try:
						ActionChains(self.browser_session).move_to_element(self.browser_session.find_elements_by_xpath('//*[@onmouseover="alert(' + token + ')"]')[0]).perform()
					except IndexError:
						pass

				if re.search('src', event, re.IGNORECASE):
						time.sleep(0.25)
			#WebDriverWait(self.browser_session, timeout=0.02).until(EC.alert_is_present())
			self.browser_session.refresh()
			return self._attempt_accept_payload(token)
		except TimeoutException:
			return False
		except UnexpectedAlertPresentException as alert:
			if token.strip('0') in alert.msg:
				self._attempt_accept_payload()
				return True
			else:
				return self._attempt_accept_payload(token)
		except (JavascriptException, NoSuchElementException) as e:
			if self._attempt_accept_payload(token):
				return True
			ttl -= 1
			if ttl == 0:
				return False
			return self._check_alert_on_page(events, token, ttl)
		except WebDriverException as e:
			print(str(e))
			if str(e) == 'Failed to convert data to an object':
				ttl -= 1
				return self._check_alert_on_page(events, token, ttl)


	def _safe_get(self, url, payload=None, login=False):
		try:
			#url = url.split('?')[0]+'?' if '?' in url else url
			url_idx = -1
			if url not in self.internal_urls:
				for internal_url in self.internal_urls:
					if internal_url in url and url.split('?')[0] in internal_url:
						url_idx = self.internal_urls.index(internal_url)
						break
			else:
				url_idx = self.internal_urls.index(url)
			if url_idx == -1:
				self.internal_urls.append(url)
				url_idx = self.internal_urls.index(url)
				self.features = np.append(self.features, [[0, 0, 0]], axis=0)
			if self.features[url_idx][0] != 0 and not login:
				url_login = self.features[url_idx][0]
				login_details = self.logins[list(self.logins)[url_login - 1]]
				usr_login =  payload if payload is not None and payload in self.current_login else list(self.logins)[url_login - 1]
				self.login(usr_login, login_details)
			time.sleep(0.1)
			self.browser_session.get(url)
			self.browser_session.current_url
		except UnexpectedAlertPresentException:
			self._attempt_accept_payload()
			self.browser_session.get(url)
			self._attempt_accept_payload()
		except:
			self.browser_session = self._instansiate_test_sess(self.browser, True)
			self._safe_get(url)

	def _get_browser_page_with_dependency(self, url):
		while self.browser_session.current_url != url or 'HTTP ERROR' in self.browser_session.page_source:
			self._safe_get(url)
			page_to_url = [self.internal_urls[i] for i in range(self.transition_tags.shape[0]) if
							  self.transition_tags[i, self.internal_urls.index(url)] != ''][0]
			tag_info = self.transition_tags[self.internal_urls.index(page_to_url)][
				self.source_idx]
			while 'HTTP ERROR' in self.browser_session.page_source or self.browser_session.current_url != url:
				self._safe_get(page_to_url)
				# self.browser_session.get(page_to_url)
				try:
					self.browser_session.find_element_by_xpath('//input[@value="' + tag_info['value'] + '"]').click()
				except:
					if self.features[self.source_idx][0] == 1:
						#self.browser_session.get(self.logins[list(self.logins)[0]][0])
						self.login(self.logins[list(self.logins)[0]][0], self.logins[list(self.logins)[0]])

				tag_info = self.transition_tags[self.internal_urls.index(self.browser_session.current_url)][
					self.internal_urls.index(page_to_url)]
				page_to_url = [self.internal_urls[i] for i in range(self.transition_tags.shape[0]) if
								  self.transition_tags[i, self.internal_urls.index(url)] != ''][0]

	def _send_payload_browser(self, payload, events=None, token=None):
		if self.logged_in == True:
			#self.logout_browser_session()
			self.logout()
		#if token != None:
		#	events = ['', '']
		#	payload = '<script>alert('+token+')</script>'
		self._safe_get(self.source)
		self._get_browser_page_with_dependency(self.source)


		if re.search('register|signup|sign_up', self.source, re.IGNORECASE):
			new_filler = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(6))
			for key in self.input_names:
				if re.search('username', key, re.IGNORECASE):
					self.input_names[key] = new_filler
					self.filler = new_filler
				# elif re.search('password', key, re.IGNORECASE):
				#	self.input_names[key] = self.password
				elif re.search('email', key, re.IGNORECASE):
					self.input_names[key] = new_filler + '@email.com'
					self.filler = new_filler

		self.filler
		if 'URL'in self.input_names.keys():
			source = self.source
			for name in self.input_names['URL']:
				if name[0] == self.injection_form:
					source += name[0] +'='+ payload + '&'
				else:
					source += name[0] + '=' + ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(6)) + '&'
			source = source[:-1]
			self._safe_get(source)
		else:
			for name in self.input_names:
				if len(self.browser_session.find_elements_by_name(name)) == 0:
					if self.current_login and self.features[self.sink_idx][0] != 0:
						login_acc = self.current_login[list(self.current_login)[0]]
						for usr_login in self.logins.keys():
							self.login(usr_login, login_acc)
						self._safe_get(self.source)
				input = self.browser_session.find_element_by_name(name)
				if name == self.injection_form:

					try:
						input.send_keys(payload)
					except:
						if input.is_displayed() == False:
							try:
								input.find_element_by_xpath(
									'.//ancestor::div//*[@type="checkbox"]').click()
							except:
								for element in input.find_elements_by_xpath('.//ancestor::div//option'):
									element.click()
									if input.is_displayed():
										break
						if input.is_displayed() or input.get_attribute('type') != 'hidden':
							try:
								input.send_keys(payload)
							except:
								if input.get_attribute('value')  != '':
									self.browser_session.execute_script('document.getElementsByName("'+name+'")[0].value="'+payload+'";')

				elif 'submit' not in name and input.get_attribute('type') != 'hidden' and input.get_attribute('type') != 'submit' and input.get_attribute('value') != self.input_names[name]:
					try:
						input.send_keys(self.input_names[name])
					except:
						pass
				# input.send_keys(payload)
				# if self.source == self.sink:
				self._attempt_accept_payload()

			if len(input.find_elements_by_xpath('.//ancestor::form')) > 0:

				if len(input.find_elements_by_xpath('.//ancestor::form')[-1].find_elements_by_xpath(
						'.//*[@type="submit"]')) > 0:
					try:
						if input.find_elements_by_xpath('.//ancestor::form')[-1].find_element_by_xpath(
						'.//*[@type="submit"]').is_displayed() == False:
							input.find_elements_by_xpath('.//ancestor::form')[-1].find_element_by_xpath(
								'.//*[@type="submit"]//ancestor::div//*[@type="checkbox"]').click()

						input.find_elements_by_xpath('.//ancestor::form')[-1].find_elements_by_xpath(
						'.//*[@type="submit"]')[-1].click()
					except:
						pass
				else:
					input.submit()
			elif len(input.find_elements_by_xpath('.//ancestor::div//input')) > 0:

				if len(input.find_elements_by_xpath('.//ancestor::div')[-1].find_elements_by_xpath(
						'.//input[@type="submit"]')) > 0:
					input.find_elements_by_xpath('.//ancestor::div')[-1].find_element_by_xpath(
						'.//input[@type="submit"]').click()
				else:
					input.submit()

		if len(self.dependency) > 1:
			# print('theres a page dependency!')
			dependency_urls = list(self.dependency)
			if self.browser_session.current_url != dependency_urls[1]:
				self._safe_get(dependency_urls[0], payload)
				for idx in range(1, len(dependency_urls)):
					if len(self.dependency[dependency_urls[idx]]) > 0:
						try:
							self.browser_session.find_element_by_xpath('//form[@action="/' + self.actions[idx] + '"]//input[@type="submit"]').submit()
						except:
							try:
								self.browser_session.find_element_by_xpath('//form[@action="' + self.actions[idx] + '"]//input[@type="submit"]').submit()
							except:
								print('possible error in locating dependency in selenium')
								self.browser_session.get(dependency_urls[idx])

			else:
				for idx in range(2, len(dependency_urls)):
					if len(self.dependency[dependency_urls[idx]]) > 0:
						try:
							self.browser_session.find_element_by_xpath('//form[@action="/' + dependency_urls[idx].split(self.domain)[-1] + '"]//input[@type="submit"]').submit()
						except:
							try:
								self.browser_session.find_element_by_xpath('//form[@action="/' + dependency_urls[idx].split(self.domain)[-1] + '"]//input[@type="submit"]').submit()
							except:
								self.browser_session.find_element_by_xpath('//form[@action="/' + dependency_urls[idx+1].split(self.domain)[-1] + '"]//input[@type="submit"]')
		# print("got to:" + self.browser_session.current_url)
		elif re.search('signup|register', self.source) or self.features[self.sink_idx][
			0] != 0:
			if re.search('signup|register', self.source) and 'password' in self.input_names:
				if self.password is not None:
					for usr_login in self.logins.keys():
						login_acc = [self.logins[usr_login][0], self.password]
						usr_login = payload if re.search('username', self.injection_form,
														 re.IGNORECASE) else self.filler
						self.login(usr_login, login_acc)
						self._safe_get(self.internal_urls[0])
						self.browser_session.get(self.sink)
						self.browser_session.refresh()
						if events is not None:
							check = self._check_alert_on_page(events, token, ttl=6)
							if check == True:
								return True
						# self.logout_browser_session()
						# self.logout()
			elif self.current_login and self.features[self.sink_idx][0] != 0:
				login_idx = self.features[self.sink_idx][0]
				login_acc = self.logins[list(self.logins)[login_idx - 1]]
				for usr_login in self.logins.keys():
					self.login(usr_login, login_acc)
					self._safe_get(self.internal_urls[0])
					self.browser_session.get(self.sink)

		elif self.browser_session.current_url.split('?')[0] not in self.sink:
			if self.features[self.sink_idx][0] != 0:
				sink_login = self.features[self.sink_idx][0]
				login_details = self.logins[list(self.logins)[sink_login - 1]]
				self.login(list(self.logins)[sink_login - 1], login_details)
				self._safe_get(self.internal_urls[0])
				self.browser_session.get(self.sink)
			else:
				self._safe_get(self.internal_urls[0])
				self.browser_session.get(self.sink)

		#self.browser_session.refresh()



	def check_dom_xss(self, rand_string):
		if list(self.input_names)[0] == '':
			return None
		self._send_payload_browser(payload=rand_string)
		if rand_string in self.browser_session.page_source:
			return self.get_escape_string(self.browser_session.page_source, rand_string)
		else:
			return None

	def test_payload_alert_interaction(self, payload, events, token):
		# test the payload to determine if it triggers an alert.
		# try to locate the alert and accept it.
		try:
			#payload = '\' onmouseover=alert(1) '; events = ['onomouseover','']; token = '1'
			self._send_payload_browser(payload, events=events,token=token)
			#self.test_session.get(self.site_to_fuzz)
			self.browser_session.refresh()
			check = self._check_alert_on_page(events, token, ttl=6)
			if self.logged_in == True:
				#self.logout_browser_session()
				self.logout()
			return check
		except UnexpectedAlertPresentException as alert:
			#print('Alert 2')
			if token.strip('0') in alert.msg:
				self._attempt_accept_payload()
				return True
			else:
				return self._attempt_accept_payload(token)

	def _send_payload(self, payload, site=None, start=True):
		if site == None:
			source = self.sink
			source_idx = self.source_idx
		else:
			source = site
			if source not in self.internal_urls:
				source_idx = None
				for url in self.internal_urls:
					if source in url:
						source_idx = self.internal_urls.index(url)
						break
				if source_idx == None:
					source_idx = self.source_idx
			else:
				source_idx = self.internal_urls.index(source)
		if self.sink == self.source:
			if self.features[source_idx][0]:
				if payload in self.current_login.keys():
					self.login(list(self.current_login)[0], self.current_login[list(self.current_login)[0]])
				else:
					login_idx = self.features[source_idx][0] - 1
					login_site = list(self.logins)[login_idx]
					self.login(login_site, self.logins[login_site])
				blank_request = self.text_session.get(source)
				#self.logout()
			else:
				try:
					blank_request = self.text_session.get(source)
				except:
					print('error occured getting page')
					time.sleep(0.5)
					blank_request = self.text_session.get(source)

		else:
			if self.features[self.sink_idx][0]:
				if payload in self.current_login.keys():
					self.login(list(self.current_login)[0], self.current_login[list(self.current_login)[0]])
				else:
					login_idx = self.features[self.sink_idx][0] - 1
					usr_login = list(self.logins)[login_idx]
					self.login(usr_login, self.logins[usr_login])
				blank_request = self.text_session.get(self.sink)
				#self.logout()
			else:
				blank_request = self.text_session.get(self.sink)
		if len(self.dependency) > 1 and source in self.dependency:


			form_parameters = {input_name:payload if (self.dependency[source][input_name] == '' and payload not in self.current_login) or input_name == self.injection_form or self.dependency[source][input_name] == None else self.dependency[source][input_name] for input_name in self.dependency[source].keys()}
		else:
			form_parameters = {input_name:payload if self.input_names[input_name] == '' or input_name == self.injection_form or self.input_names[input_name] == None else self.input_names[input_name] for input_name in self.input_names.keys()}


		if re.search('register|signup|sign_up', source, re.IGNORECASE) and start == False:
			new_filler = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(6))
			for key in form_parameters.keys():
				if re.search('username', key, re.IGNORECASE):
					if re.search('username', self.injection_form, re.IGNORECASE) is None:
						form_parameters[key] = new_filler
						self.filler = new_filler
				elif re.search('email', key, re.IGNORECASE):
					if re.search('email', self.injection_form, re.IGNORECASE) is None:
						form_parameters[key] = new_filler + '@email.com'
						self.filler = new_filler

		if re.search('email', self.injection_form, re.I):
			form_parameters[self.injection_form] = form_parameters[self.injection_form] + '@email.com'

		if 'URL' in self.input_names.keys():
			for name in self.input_names['URL']:
				if name[0] == self.injection_form:
					source += name[0] + '=' + payload + '&'
				else:
					source += name[0] + '=' + ''.join(
						random.choice(string.ascii_uppercase + string.digits) for _ in range(6)) + '&'
			source = source[:-1]
			payload_request = self.text_session.get(source)
		elif self.form_method == 'get':
			if self.split == False:
				payload_request = self.text_session.get(source, params=form_parameters)
			else:
				payload_request = self.text_session.get(source.split('?')[0], params=form_parameters)
		elif self.form_method == 'post':
			if self.split == False:
				payload_request = self.text_session.post(source, data=form_parameters)
			else:
				payload_request = self.text_session.post(source.split('?')[0], data=form_parameters)

		return blank_request, payload_request.url, payload_request

	#send payload to the site
	def send_payload(self, payload):

		if self.dom_based == True:
			if self.logged_in == True:
				#self.logout_browser_session()
				self.logout()
			# events = ['', '']
			# payload = '<script>alert('+token+')</script>'
			try:
				self._safe_get(self.source)
			except:
				print('get page error')
			while self.browser_session.current_url != self.source or 'HTTP ERROR' in self.browser_session.page_source:
				self._safe_get(self.source)
				page_to_source = [self.internal_urls[i] for i in range(self.transition_tags.shape[0]) if
								  self.transition_tags[i, self.source_idx] != ''][0]
				tag_info = self.transition_tags[self.internal_urls.index(page_to_source)][
					self.source_idx]
				while 'HTTP ERROR' in self.browser_session.page_source or self.browser_session.current_url != self.source:
					self._safe_get(page_to_source)
					# self.browser_session.get(page_to_source)
					self.browser_session.find_element_by_xpath('//input[@value="' + tag_info['value'] + '"]').click()
					tag_info = self.transition_tags[self.internal_urls.index(self.browser_session.current_url)][
						self.internal_urls.index(page_to_source)]
					page_to_source = [self.internal_urls[i] for i in range(self.transition_tags.shape[0]) if
									  self.transition_tags[i, self.source_idx] != ''][0]
			blank_response = self.browser_session.page_source
			try:
				self._send_payload_browser(payload)
				payload_response = self.browser_session.page_source
				payload_returned = ''.join([li for li in difflib.ndiff(payload_response.splitlines(), blank_response.splitlines()) if li[0] not in ' ?+'])
				return payload_returned, self.browser_session.page_source
			except UnexpectedAlertPresentException:
				self._attempt_accept_payload()
				payload_response = self.browser_session.page_source
				payload_returned = ''.join([li for li in difflib.ndiff(payload_response.splitlines(), blank_response.splitlines()) if li[0] not in ' ?+'])
				return payload_returned, self.browser_session.page_source

		for dependency in self.dependency.keys():
			blank_response, returned_url, payload_response = self._send_payload(payload, dependency, start=False)
			if re.search('signup|register', self.source) and payload not in self.current_login:
				if re.search('signup|register', self.source) and 'password' in self.input_names:
					for usr_login in self.logins.keys():
						login_acc = [self.logins[usr_login][0], self.password]
						usr_login = payload if re.search('username', self.injection_form, re.IGNORECASE) else self.filler
						self.login(usr_login, login_acc)
						payload_response = self.text_session.get(self.sink)
						self.logout()
				elif self.current_login and self.features[self.sink_idx][0] != 0:
					login_acc = self.current_login[list(self.current_login)[0]]
					for usr_login in self.logins.keys():
						self.login(usr_login, login_acc)
						payload_response = self.text_session.get(self.sink)
						self.logout()

			if returned_url.split('?')[0] not in self.sink:
				new_url, new_inputs = self._get_dependant_form_info(payload_response.url, payload_response.content)
				if new_url in self.dependency.keys():
					self.dependency[new_url] = new_inputs
				elif new_url.split('?')[0] in self.dependency.keys():
					self.dependency[new_url.split('?')[0]] = new_inputs
				else:
					print('new key?')

		# if the sink is not current page, get current sink as stored xss
		if self.sink.split('?')[0] not in payload_response.url and blank_response.status_code != 404 and re.search('signup|register', self.source) is None:
			payload_response = self.text_session.get(self.sink)
		elif re.search('signup|register', self.source) and self.current_login and self.sink.split('?')[0] not in payload_response.url:
			usr_login = list(self.current_login)[0]

			self.login(usr_login, self.current_login[usr_login])
			payload_response = self.text_session.get(self.sink)

		payload_returned = ''.join([li for li in difflib.ndiff(payload_response.text.splitlines(), blank_response.text.splitlines()) if li[0] not in ' ?+'])
		for strippable in self.to_strip_from_payload:
			payload_returned = payload_returned.replace(strippable, '')

		return payload_returned, payload_response.text



	def _login(self):
		with requests.Session() as sess:
			if 'Goat' in self.domain:
				payload = {
					'username': 'adminroot',
					'password': 'password',
					'matchingPassword': 'password',
					'agree': 'agree'}
				req = sess.post(self.domain + 'register.mvc', data=payload)
				if re.search('User already exists', req.text):
					req = sess.post(self.domain + 'login', data=payload)
				print('GOAT agent not configured yet...')
				exit()
				return sess
			elif 'bwapp' in self.domain:
				difficulty = {'low':'0', 'medium':'1', 'high':'2' }
				payload ={
					'login': 'bee',
					'password': 'bug',
					'security': self.difficulty,
					'security_level': difficulty[self.difficulty],
					'form': 'submit'
				}
				req = sess.post(self.domain + '/login.php', data=payload)
				return sess
			elif 'dvwa' in self.domain:
				payload = {
					'username': 'admin',
					'password': 'password',
					'Login': 'Login'}
				req = sess.get(self.domain + '/login.php')
				token = re.search("user_token'\s*value='(.*?)'", req.text).group(1)
				payload['user_token'] = token
				sess.post(self.domain + '/login.php', data=payload)
				req = sess.get('http://localhost/dvwa/setup.php')
				payload ={'create_db': 'Create+/+Reset+Database'}
				payload['user_token'] = re.search("user_token'\s*value='(.*?)'", req.text).group(1)
				sess.post('http://localhost/dvwa/setup.php', data=payload)
				req = sess.get('http://localhost/dvwa/security.php')
				payload ={
					'security': self.difficulty,
					'seclev_submit': "Submit"
				}
				payload['user_token'] = re.search("user_token'\s*value='(.*?)'", req.text).group(1)
				sess.post('http://localhost/dvwa/security.php', data=payload)
				return sess
			else:
				return sess

	def login(self, login_usrname, login_details):
		login_url, usr_pword = login_details
		if self.logged_in == True:
			self.logout()
		self._safe_get(login_url, login=True)
		while self.browser_session.current_url != login_url and not re.search('signin|login', self.browser_session.current_url, re.I):
			self._safe_get(login_url, login=True)
		self.current_login = {login_usrname: [login_url, usr_pword]}
		if usr_pword == None:
			print('error')
		self.logged_in = True
		try:
			text_page = html.fromstring( self.text_session.get(login_url).text)
		except:
			text_page = html.fromstring(self.browser_session.page_source)
		if len(self.browser_session.find_elements_by_xpath("//input[@type='password']/ancestor::form")) > 0:
			input_tags = self.browser_session.find_elements_by_xpath("//input[@type='password']/ancestor::form")[
				-1].find_elements_by_xpath('.//input')
		elif len(self.browser_session.find_elements_by_xpath("//input[@type='password']/ancestor::div")) > 0:
			input_tags = self.browser_session.find_elements_by_xpath("//input[@type='password']/ancestor::div")[
				-2].find_elements_by_xpath('.//input')
		else:
			input_tags = self.browser_session.find_elements_by_xpath("//input[@type='password']/ancestor::*")[
				-3].find_elements_by_xpath('.//input')
		tag_names = [tag.get_attribute('name') for tag in input_tags if tag.get_attribute('name') != '']
		login_data = {}
		for name in tag_names:
			if re.search('password|pwd', name, re.IGNORECASE):
				login_data[name] = usr_pword
				self.browser_session.find_element_by_name(name).send_keys(usr_pword)
			elif re.search('name|user', name, re.IGNORECASE):
				login_data[name] = login_usrname
				self.browser_session.find_element_by_name(name).send_keys(login_usrname)
			elif re.search('email', name, re.IGNORECASE):
				login_data[name] = login_usrname + '@email.com' if '@' not in login_usrname else login_usrname
				self.browser_session.find_element_by_name(name).send_keys(login_data[name])
			elif re.search('signin|log', name, re.IGNORECASE) and self.browser_session.find_element_by_name(name).get_attribute('value') == '':
				login_data[name] = login_usrname
				self.browser_session.find_element_by_name(name).send_keys(login_usrname)
			else:
				login_data[name] = text_page.xpath('//*[@name="'+name+'"]')[0].value
				#login_data[name] = self.browser_session.find_element_by_name(name).get_attribute('value')


		login_url = text_page.xpath('//*[@name="' + name + '"]/ancestor::form/@action')[0] if text_page.xpath('//*[@name="' + name + '"]/ancestor::form/@action') != [''] else self.browser_session.current_url
		if login_url in login_details[0]:
			login_url = login_details[0]
		if len(self.browser_session.find_elements_by_xpath("//input[@type='password']/ancestor::form")) > 0:
			self.browser_session.find_elements_by_xpath('//input[@type="password"]/ancestor::form')[-1].find_element_by_xpath(
				'.//descendant::*[@type="submit"]').click()
		elif len(self.browser_session.find_elements_by_xpath("//input[@type='password']/ancestor::div")) > 0:
			self.browser_session.find_elements_by_xpath('//input[@type="password"]/ancestor::div')[-2].find_element_by_xpath(
				'.//descendant::*[@type="submit"]').click()
		elif len(self.browser_session.find_elements_by_xpath('//button[contains(@*, "login")]')) > 0:
			self.browser_session.find_element_by_xpath('//button[contains(@*, "login")]').click()
		else:
			self.browser_session.find_elements_by_xpath('//input[@type="password"]/ancestor::*')[-3].find_element_by_xpath(
				'.//descendant::*[@type="submit"]').click()

		self.text_session.post(login_url, data=login_data)

	def logout_browser_session(self):
		self._safe_get(self.internal_urls[0])
		self.browser_session.find_element_by_xpath('//*[@href="' + self.logout_link + '"]').click()

	def logout(self):
		logout_link = []
		#while len(logout_link) == 0:
		payload_tree = ''
		while type(payload_tree) == str:
			try:
				page_source = self.text_session.get(self.internal_urls[0])
				payload_tree = html.fromstring(page_source.content)
			except:
				try:
					self.browser_session.get(self.internal_urls[0])
					payload_tree = html.fromstring(self.browser_session.page_source)
				except:
					pass
		page_links = payload_tree.xpath('//*/@href')
		logout_link = [url for url in page_links if re.search('logout|sign_out|signout', url, re.IGNORECASE)]
		if len(logout_link) != 0:
			logout_link = logout_link[0]
			self.logout_link = logout_link
			compatable_logout_link = self.domain[:-1] + logout_link if logout_link[0] == '/' else self.domain + logout_link
			compatable_logout_link = logout_link if compatable_logout_link.count('http') > 1 else compatable_logout_link
			self.text_session.get(compatable_logout_link)
			self._safe_get(self.internal_urls[0])
			#self.browser_session.get(self.internal_urls[0])
			#page_source = self.browser_session.page_source
			#payload_tree = html.fromstring(page_source)
			#page_links = payload_tree.xpath('//*/@href')
			#logout_link = [url for url in page_links if re.search('logout|sign_out|signout', url, re.IGNORECASE)][0]
			compatable_logout_link = self.domain[:-1] + logout_link if logout_link[0] == '/' else self.domain + logout_link
			compatable_logout_link = logout_link if compatable_logout_link.count('http') > 1 else compatable_logout_link
			self.browser_session.get(compatable_logout_link)
		self.logged_in = False




