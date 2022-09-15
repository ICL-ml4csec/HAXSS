import html
import torch
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


class XSSSanitisationEnv(gym.Env):
    metadata = {'render.modes': ['console']}

    def __init__(self, action_space, string_seed, context, rank, parent_tag, update_obs, transition_tags, sites, urls, source, sink, features, input_tags, transitions):
        super(XSSSanitisationEnv, self).__init__()

        self.action_space           = spaces.Discrete(action_space)
        self.observation_space      = spaces.Box(0, 3000, (1, 3), dtype=int)
        self.rank                   = rank
        self.active                 = True

        self.input_count = 0
        #initalise the encoding of the value
        self.html_encoded = False
        self.utf8_encoded = False
        self.url_encoded = False

        #initalise the capitalisation value
        self.caps = 0


        self.sessions = Connections(transition_tags=transition_tags, site=sites, internal_urls=urls, sink=sink, login_features=features, input_tags=input_tags)

        # store the starting observation
        self.starting_observation = string_seed

        # initalise payloads found
        self.payloads_found     = {}
        self.relfected_reward   = [-1.5,-0.5]
        self.partial_reward     = [-2.25,-0.75]
        self.max_reward         = 10
        self.sub_states         = {}

        # initalise starting seed
        self.plain_text_state   = self.starting_observation
        self.text_state         = self.plain_text_state
        self.context            = context
        self.escape_tag         = parent_tag
        self.successful_plain_text      = self.plain_text_state
        self.successful_capitalisation  = self.caps
        self.successful_encoding        = self.get_encoding()
        self.token              = None
        # state: sanitised state, input state, context
        self.sub_state          = np.array([self._reduce_observation(string_seed),self._reduce_observation(string_seed), self.context])
        self.starting_sub_state = np.array([self._reduce_observation(string_seed),self._reduce_observation(string_seed), self.context])
        self.add_observation_to_states(self.sub_state[0])
        self.add_observation_to_states(self.sub_state[1])
        self.submit_all         = False
        self.update_obs         = update_obs
        self.failed_state_pairs = {}

    def set_context(self, context):
        self.context = context

    def get_state(self):
        return self.sub_states

    def set_internal_states(self, states):
        self.sub_states = states[self.rank]

    def set_plain_text_state(self, state):
        self.plain_text_state = state[self.rank]

    def set_encoding(self, encoding):
        encoding = encoding[self.rank]
        if encoding == 'html':
            self.html_encoded = True
        elif encoding == 'url':
            self.url_encoded = True
        elif encoding == 'utf8':
            self.utf8_encoded = True

    def get_encoding(self):
        if self.html_encoded:
            return 'html'
        elif self.url_encoded:
            return 'url'
        elif self.utf8_encoded:
            return 'utf8'
        else:
            return 'None'

    def seed(self, seed=None):
        self.np_random, seed = seeding.np_random(seed)
        return [seed]

    def update_active_agents(self, sanitisation):
        self.active = sanitisation[self.rank]

    def load_session(self):
        self.sessions.load_session_info(str(self.rank))

    def close_session(self):
        self.sessions.close()

    def reset(self):
        self.html_encoded = False
        self.utf8_encoded= False
        self.url_encoded= False
        self.caps = 0
        self.plain_text_state = self.starting_observation
        return self.starting_sub_state

    def store_successful_instances(self):
        self.successful_plain_text      = self.plain_text_state
        self.successful_encoding        = self.get_encoding()
        self.successful_capitalisation  = self.caps

    def get_successful_instance(self):
        return (self.successful_plain_text, self.successful_encoding, self.successful_capitalisation)


    def get_plain_payload(self):
        return self.plain_text_state

    def update_state(self, sanitised_states, contexts, plain_states):
        self.plain_text_state = plain_states[self.rank]
        self.sanitised_state = sanitised_states[self.rank]
        self.context = contexts[self.rank]
        self.sub_state = np.array([self._reduce_observation(self.plain_text_state),
                                   self._reduce_observation(self.sanitised_state), self.context])
        return torch.tensor([[self.add_observation_to_states(self.sub_state[0]), self.add_observation_to_states(self.sub_state[1]), self.context]], dtype=torch.float32)

    def update_vars(self, tokens, parent_tag):
        self.token      = tokens[self.rank]
        self.escape_tag = parent_tag

    def get_payload(self):
        return self.text_state

    def get_all_payloads_found(self):
        payload_list = []
        for keys in self.payloads_found.keys():
            payload_list.append(keys)
        print(payload_list)
        return payload_list


    def reset_payloads_found(self):
        self.payloads_found = {}

    def step(self, action):
        if not self.active:
            return np.array([self._reduce_observation(self.plain_text_state), self._reduce_observation(self.plain_text_state), self.context]), 0, False, {}
        action_type, var = self._discrete_action_to_continuous(action)


        if action_type == 'capitalise':
            if var == 'alt':
                next_state = ''
                i = True
                for char in self.plain_text_state:
                    if i:
                        next_state += char.upper()
                    else:
                        next_state += char.lower()
                    i = not i
                self.caps = 2
            elif var == 'All':
                next_state = self.plain_text_state.capitalize()
                self.caps = 1
            else:
                next_state = self.plain_text_state.lower()
                self.caps = 0
            next_state = re.sub('alert', 'alert', next_state, flags=re.I)
        elif action_type == 'rule':
            if re.search('^[\'"-;/>)]+', self.plain_text_state) is not None:
                    if var == '<' and '<<' not in self.plain_text_state and '<' in self.plain_text_state and \
                            re.search(r'<\w+', self.plain_text_state) is not None:
                        tag = re.search(r'<\w+', self.plain_text_state).group(0)
                        next_state = re.sub(tag, '<' + tag, self.plain_text_state)
                    elif var == '\\' and '\\\'' not in self.plain_text_state and '\\"' not in self.plain_text_state:
                        next_state = re.sub('\'', '\\\'', self.plain_text_state)
                        next_state = re.sub('\"', '\\"', next_state)
                    elif var == ';' and ';' not in self.plain_text_state and self.plain_text_state[0] != ' ' and '-->' not in self.plain_text_state and re.search('[\'")]+', self.plain_text_state):
                        char = re.search('[\'")]+', self.plain_text_state).group(0)
                        next_state = re.sub(re.escape(char), char + ';', self.plain_text_state)
                    elif var == '>' and re.search('^[\'"-]*[;/]*>',  self.plain_text_state) is not None:
                        match = re.search('^[\'"-]*[;/]*|^ ',  self.plain_text_state)
                        if match:
                            next_state = re.sub(match.group(0), match.group(0) + '>', self.plain_text_state)
                        else:
                            next_state = self.plain_text_state
                    else:
                        next_state = self.plain_text_state
            else:
                # insert the escape string at the beginning of the state
                if var == '<' and '<<' not in self.plain_text_state and '<' in self.plain_text_state and \
                        re.search(r'<\w+', self.plain_text_state) is not None:
                    tag = re.search(r'<\w+', self.plain_text_state).group(0)
                    next_state = re.sub(tag, '<' + tag, self.plain_text_state)
                elif var == '>' and re.search('^[\'"-]*[;/]*>', self.plain_text_state) is not None:
                    match = re.search('^[\'"-]*[;/]*|^ ', self.plain_text_state)
                    if match:
                        next_state = re.sub(match, match + '>', self.plain_text_state)
                    else:
                        next_state = self.plain_text_state
                else:
                    next_state = self.plain_text_state

        elif action_type == 'separator':
            next_state = re.sub('\s|%0C|%2F|%0D', var, self.plain_text_state)
        elif action_type == 'tag_obfuscation':
            tag_names = re.findall('</*[^\s>/]+', self.plain_text_state)
            next_state = self.plain_text_state
            for tag_name in tag_names:
                next_state = re.sub(re.escape(tag_name), tag_name[:2]+var+tag_name[2:], next_state)
        else:
            next_state = self.plain_text_state

        self.plain_text_state = next_state

        # encode the payload
        if action_type == 'encode' or self.utf8_encoded or self.url_encoded or self.html_encoded:
            if (action_type == 'encode' and var == 'html') or self.html_encoded:
                next_state = ''
                for char in self.plain_text_state:
                    next_state += '&#x' + (hex(ord(char)))[2:] + ';'
                self.html_encoded = True
            elif (action_type == 'encode' and var == 'utf8') or self.utf8_encoded:
                next_state = ''
                for char in self.plain_text_state:
                    next_state += '\\u00' + (hex(ord(char)))[2:]
                next_state = '"' + next_state + '"'
                self.utf8_encoded = True
            elif (action_type == 'encode' and var == 'URL') or self.url_encoded:
                next_state = urllib.parse.quote(self.plain_text_state)
                self.url_encoded = True
        elif action_type == 'decode':
            next_state = self.plain_text_state
            self.url_encoded = False
            self.utf8_encoded = False
            self.html_encoded = False
        elif action_type == 'bracket':
            if '(' in self.plain_text_state:
                next_state = self.plain_text_state.replace('(', '`')
                next_state = next_state.replace(')', '`')
            else:
                next_state = self.plain_text_state


        self.text_state = next_state

        encoded_next_state = self._reduce_observation(self.plain_text_state)
        if encoded_next_state in self.failed_state_pairs:
            reward = self.failed_state_pairs[encoded_next_state][0]
            done = 0
            returned_next_state = self.failed_state_pairs[encoded_next_state][1]
            info = {'requested':False}
        else:
            reward, done, returned_next_state = self._compute_reward(next_state)
            if not done:
                self.failed_state_pairs[encoded_next_state] = [reward, returned_next_state]
            info = {'requested':True}

        encoded_returned_next_state = self._reduce_observation(returned_next_state)
        if self.update_obs:
            encoded_next_state = self.add_observation_to_states(encoded_next_state)
            encoded_returned_next_state = self.add_observation_to_states(encoded_returned_next_state)
        return np.array([encoded_next_state, encoded_returned_next_state, self.context]), reward, done, info


    # function for the agent to compute its reward.
    def _compute_reward(self, next_state):

        #next_state = '<body onload=alert('+self.token + ')></body>'
        # send next_state payload to the application return the payload after sanitisation
        payload_returned, page_response = self.sessions.send_payload(next_state)


        # decode the next state to return it to non-URL encoding for comparision to payload_returned
        next_state_decoded = self.plain_text_state

        # match object
        matched_sequences = difflib.SequenceMatcher(None, next_state_decoded, payload_returned, False)

        # get all the matches of the payload and the sanitised payload.
        matches = []
        for match_set in (matched_sequences.get_matching_blocks()):
            if match_set[2] != 0 and not next_state_decoded[match_set.a:match_set.a + match_set.size].isalpha():
                matches.append(next_state_decoded[match_set.a:match_set.a + match_set.size])

        context_change =  self.sessions.check_context_change(page_response, self.escape_tag, self.token)
        # check if the payload is reflected entirely or the context has changed
        if matches and matches[0] == next_state_decoded or context_change is not None:
            if context_change is not None:
                self.context = self._context_to_n(context_change)
            self.store_successful_instances()
            return 10, 1, payload_returned
        # sparse reward setting only reward if context change or complete reflection, otherwise we give penalty
        else:
            return -1, 0, payload_returned

    # Function to convert discrete action (as used by a DQN) to a continuous action (as used by the environment).
    def _discrete_action_to_continuous(self, discrete_action):
        discrete_action = int(discrete_action)
        # action to decode URL encoding
        if discrete_action == 0:
            continuous_action = ('decode', 'decode')
        # actions to introduce special chars to escape the html
        if discrete_action in range(1, 4):
            rules = ['\\', '<', ';']
            continuous_action = ('rule', rules[discrete_action - 1])
        # capitalise every other letter in the payload
        if discrete_action == 4:
            continuous_action = ('capitalise', 'alt')
        # make all chars lowercase
        if discrete_action == 5:
            continuous_action = ('capitalise', 'None')
        # encode payload with URL encoding
        if discrete_action == 6:
            continuous_action = ('encode', 'URL')
        if discrete_action == 7:
            continuous_action = ('encode', 'utf8')
        if discrete_action == 8:
            continuous_action = ('encode', 'html')
        if discrete_action in range(9, 12):
            attribute_separators = ['%0D', '%2F', '%0C']
            continuous_action = ('separator', attribute_separators[discrete_action - 9])
        if discrete_action == 12:
            continuous_action = ('tag_obfuscation', '%00')
        if discrete_action == 13:
            continuous_action = ('bracket', '`')
        return continuous_action


    def _reduce_observation(self, state):
        encoded_state = re.sub(r'[0-9]', '', state)
        encoded_state = encoded_state.replace('\\', '\\')
        encoding = {'src': 0, 'onLoad': 1, 'onKeyPress': 2, 'onClick': 3, 'onMouseOver': 4, 'onerror': 5, '%':32,
                    'img': 6, 'script': 7, 'link': 8, 'style': 9, 'body': 10, '<a': 11, 'a>': 11, 'href': 23,
                    '<': 12, '>': 13, '}': 14, '\)': 15, "'": 16, '"': 17, '-': 18, '/': 19, ';': 20, '>': 21, '\\':22}
        for key in encoding:
            if re.search(re.escape(key), self.plain_text_state, re.IGNORECASE):
                pattern = re.compile(re.escape(key), re.IGNORECASE)
                matches = pattern.findall(encoded_state)
                for match in matches:
                    encoded_state = encoded_state.replace(match, str(encoding[key]))
        encoded_state = re.sub(r'[^0-9]', '', encoded_state)


        if self.caps == 0:
            encoded_state += str(24)  # no capitalisation
        elif self.caps == 1:
            encoded_state += str(25)  # capitalisation
        elif self.caps == 2:
            encoded_state += str(26)  # alternating capitalisation
        if self.utf8_encoded:
            encoded_state += str(27)  # utf8 encoded
        if self.html_encoded:
            encoded_state += str(29)
        if self.html_encoded:
            encoded_state = re.sub(r'17', '', encoded_state)
            encoded_state += str(30)  # URL encoded
        else:
            encoded_state += str(31)  # not URL encoded
        encoded_state = int(encoded_state)

        return encoded_state

    def add_observation_to_states(self, observation):
        if observation in self.sub_states.keys():
            feature_representation = self.sub_states[observation]
        else:
            feature_representation = max(self.sub_states.values(), default=0) + 1
            self.sub_states[observation] = feature_representation
        return feature_representation


    # func to remove the URL encoding of the state
    def url_decode(self, state):
        return urllib.parse.unquote(state)


    def json_decode(self, state):
        return json.loads(state)


    def html_decode(self, state):
        return html.unescape(state)


    def _context_to_n(self, context):
        if context == 'javascript':
            return 0
        elif context == 'comment':
            return 1
        elif context == 'attribute':
            return 2
        elif context == 'tag':
            return 3


