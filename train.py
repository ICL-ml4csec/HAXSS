from dqn.run_agent import run_policy
from crawling.crawler import  Crawler
import json
import numpy as np
from pathlib import Path
import argparse
import re
import random
import art

def train_haxss():
        parser = argparse.ArgumentParser()
        parser.add_argument('--url', help='url to train on', type=str)
        parser.add_argument('--processes', help='number of processes to use, default = 4', type=int, default=4)
        parser.add_argument('--gamma', help='discount factor, default = 0.99', type=float, default=0.99)
        parser.add_argument('--epsilon', help='exploration factor start value, default = 1', type=float, default=1)
        parser.add_argument('--batch-size', help='batch size, default = 100', type=int, default=100)
        parser.add_argument('--episode-len', help='episode length, default = 10', type=int, default=10)
        parser.add_argument('--tlen', help='number of episodes to train for, default = 1000', type=int, default=1000)
        parser.add_argument('--update-step', help='number of episodes between target network updates, default = 50', type=int, default=50)
        parser.add_argument('--alpha', help='learning rate, default = 0.005', type=float, default=0.005)
        parser.add_argument('--login', help='login details of the format: username:password')
        parser.add_argument('--bypass_episode_len', help='episode length for secondary agent, default = 5 ', type=int, default=5)
        parser.add_argument('--max-bypass-attempts', help='max number of episodes to attempt bypass, default = 3 (15 attemtps over 3 episodes)', type=int, default=3)
        parser.add_argument('--min-xss', help='min number of xss to find in the range of --xss_range, default = 7', type=int, default=7)
        parser.add_argument('--xss-range', help='number of prior episodes to find the required number of xss in min_xss, default = 10', type=int, default=10)
        parser.add_argument('--max-episodes', help='max number of episodes before fuzzing different source-sink, default = 200', type=int, default=200)
        args = parser.parse_args()
        site = args.url
        if re.search('https?://.*(/|\.\w+)', site, re.I) is None:
            print('Please input in the following format:')
            print('http://example.com/')
            print('https://second-example.com/path/to/file.php')
            exit(0)

        '''crawler = Crawler(domain=site)
        if args.login:

            crawler.current_login = [args.login.split(':')[0], args.login.split(':')[1]]
            crawler.crawl()
            crawler.attempt_login()
        crawler.crawl()
        crawler.attempt_login()
        new_input_transitions = np.ones(crawler.input_transitions.shape)
        prev_input_transitions = np.zeros(crawler.input_transitions.shape)
        new_transitions = np.ones(crawler.transition_matrix.shape)
        prev_transitions = np.zeros(crawler.transition_matrix.shape)
        while not np.array_equal(prev_input_transitions, new_input_transitions) and  \
                not np.array_equal(prev_transitions, new_transitions):
            prev_transitions = crawler.transition_matrix
            prev_input_transitions = crawler.input_transitions
            crawler.crawl()
            crawler.crawl(discover_inputs=False)
            new_transitions = crawler.transition_matrix[:prev_transitions.shape[0], :prev_transitions.shape[1]]
            new_input_transitions = crawler.input_transitions[:prev_input_transitions.shape[0], :prev_input_transitions.shape[1]]
        crawler.close()
        login_details = {}
        for entry in crawler.login_details:
            if type(entry) != list and len(entry) > 0:
                flipped_entry = {value[0]: [key, value[1]] for key, value in entry.items()}
                for email in flipped_entry:
                    login_details[email] = flipped_entry[email]
                #acc = list(flipped_entry)
                #login_details[acc] = flipped_entry[acc]
        with open('./crawling/crawl_info/login_details.json', 'w') as outfile:
            json.dump(login_details, outfile)
        np.save('./crawling/crawl_info/transition_matrix', crawler.transition_matrix, True)
        np.save('./crawling/crawl_info/urls_found', np.array(crawler.internal_urls), True)
        np.save('./crawling/crawl_info/transition_tags', crawler.tags_that_transition, True)
        np.save('./crawling/crawl_info/features', crawler.features, True)
        np.save('./crawling/crawl_info/input_transitions', crawler.input_transitions, True)
        np.save('./crawling/crawl_info/input_tags', crawler.input_transition_tags, True)'''
        with open('./crawling/crawl_info/urls_found.npy', 'rb') as f:
            urls = list(np.load(f, allow_pickle=True))
        with open('./crawling/crawl_info/input_tags.npy', 'rb') as f:
            input_tags = np.load(f, allow_pickle=True)
        with open('./crawling/crawl_info/input_transitions.npy', 'rb') as f:
            input_matrx = np.load(f, allow_pickle=True)
        with open('./crawling/crawl_info/transition_tags.npy', 'rb') as f:
            transition_tags = np.load(f, allow_pickle=True)
        with open('./crawling/crawl_info/features.npy', 'rb') as f:
            feature_matrix = np.load(f, allow_pickle=True)
        login_file = Path('./crawling/crawl_info/login_details.json')
        if login_file.exists() and login_file.is_file():
            with open('./crawling/crawl_info/login_details.json', 'r') as infile:
                login_details = json.load(infile)
        else:
            login_details = {}
        run_policy(domain=site, processes=args.processes , urls=urls, input_tags=input_tags, transition_tags=transition_tags,
                   input_transitions=input_matrx, login_details=login_details, features=feature_matrix,
                   gamma=args.gamma,
                   batch_size=args.bsize,
                   update_step=args.upstep,
                   episode_length=args.eplen,
                   learning_rate=args.alpha,
                   train_length=args.tlen,
                   bypass_ep_len=args.bypass_episode_len,
                   max_bypass_attempts=args.max_bypass_attempts,
                   min_xss= args.min_xss,
                   xss_range = args.xss_range,
                   max_episodes= args.max_episodes,
                   train=True)

if __name__ == '__main__':
    print('=' * 70)
    font = random.choice(['tarty1', 'sub-zero', 'small', 'merlin1', 'epic', 'lildevil','lean', '3d_diagonal', 'fire_font-s'])
    art.tprint("HAXSS", font=font)
    print('='*70)
    art.tprint("======== Hierarchical Agents for XSS =========", font="fancy143")
    print('======= A reinforcement learning based XSS injection prototype =======')
    print('=' * 70)
    train_haxss()


