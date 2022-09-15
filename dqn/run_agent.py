import os.path
import time

from matplotlib import pyplot as plt
import numpy as np
from env.environ_utils import make_envs_as_vec, list_to_tensor
from dqn.multi_dqn_agent import Agent
from collections import deque
from buffers import PriorityReplayBuffer, ReplayBuffer
#from env.xss_crawl_env import XSSCrawlEnv
from env.xss_crawl_env1 import XSSCrawlEnv
from env.xss_crawl_env2 import XSSSanitisationEnv
import pickle
import tracemalloc

tracemalloc.start()

import sys

def success_cond(xss, ep, ep_this_form, train, xss_range, min_xss):
    if train:
        return ep_this_form > 30 and any(min_xss <= xss[ep - 1] - xss[ep - xss_range])
    else:
        return any(min_xss <= xss[ep - 1] - xss[ep])

def fail_cond(ep_lim, ep, xss, ep_this_form, train, xss_range, min_xss):
    if train:
        return ep_lim < ep_this_form and  any(min_xss >= xss[ep - 1] - xss[ep - xss_range])
    else:
        return ep_lim < ep_this_form


def run_policy(gamma= 0.99, batch_size= 100, update_step= 50,
               episode_length= 10, reward_correct= 10, reward_reflect= [-1.5,-0.5],
               reward_partial= [-2.25,-0.75], learning_rate= 0.005,
               priority= True, seed = '', domain=None, processes=1, urls=None,
               input_transitions=None, input_tags=None, login_details=None,
               features=None, transition_tags=None, train=False, train_length=1000,
               max_attempts=None, agent_2_batch_size=20, max_episodes=None,
               bypass_ep_len=None, max_bypass_attempts=None, min_xss=None, xss_range=None):

    if domain is None or urls is None or input_transitions is None or input_tags is None:
        print('Requires domain to fuzz...')
        sys.exit(-1)
    # trained without tag end action!
    num_actions_1 = 18
    num_actions_2 = 14
    max_a2_actions = bypass_ep_len
    max_a2_episodes = max_bypass_attempts

    agent_1 = Agent(num_actions_1, epsilon=0.05, lr=learning_rate, batch_size=batch_size,
                  model='dqn', rnd=True, processes=processes, input_dimension=2)

    agent_2 = {action: Agent(num_actions_2, epsilon=0.05, lr= 0.005,
                                            batch_size=agent_2_batch_size, model='dqn', rnd=False, processes=1, input_dimension=3) for
                              action in range(num_actions_1)}
    if not (os.path.exists(os.path.abspath(os.path.join(__file__ + '/../../saved_models/HAXSS/training_data')))):
        os.mkdir(os.path.abspath(os.path.join(__file__ + '/../../saved_models/HAXSS/training_data')))
    if not (os.path.exists(os.path.abspath(os.path.join(__file__ + '/../../saved_models/HAXSS/testing_data')))):
        os.mkdir(os.path.abspath(os.path.join(__file__ + '/../../saved_models/HAXSS/testing_data')))
    if train == False:
        print('Loading HAXSS weights...')
        agent_1.load_model(relative_path='./saved_models/HAXSS/agent_1.pt')
        for key in agent_2:
            agent_2[key].load_model(relative_path='./saved_models/HAXSS/agent_2/agent_2_'+str(key)+'.pt')
    print('Loaded HAXSS weights')
    print('Spinning up envrionments...')




    environments_1 = make_envs_as_vec(action_space=num_actions_1, seed=seed, gamma=gamma,
                                      processes=processes,
                                      sites=(domain),
                                      input_tags=input_tags, urls=urls, transition_tags=transition_tags,
                                      transitions=input_transitions, env=XSSCrawlEnv, login=login_details,
                                      features=features)
    source, sink = environments_1.env_method('get_source_sink')[0]
    sites = (domain, source)

    environments_2 = make_envs_as_vec(action_space=num_actions_2, seed=seed, gamma=gamma, processes=processes, sites=sites,
                                      env=XSSSanitisationEnv, login=login_details,
                                      context=environments_1.env_method('get_context')[0],
                                      parent_tag=environments_1.env_method('get_escape_tag')[0], input_tags=input_tags, urls=environments_1.env_method('get_internal_urls')[0],
                                      transition_tags=transition_tags, transitions=input_transitions, features=features, source=source, sink=sink)
    with open('./saved_models/HAXSS/env_1_states.pkl', 'rb') as f:
            states = pickle.load(f)
            environments_1.env_method('set_internal_states', states)
    with open('./saved_models/HAXSS/env_2_states.pkl', 'rb') as f:
            sub_states = pickle.load(f)
            environments_2.env_method('set_internal_states', sub_states)

    print('Loaded envrionments')

    state = environments_1.reset()
    xp_buffer_1 = PriorityReplayBuffer()
    xp_buffers_2 ={action: ReplayBuffer() for action in range(len(agent_2))}

    start_time = time.time()

    print('Exploring for ' + str(agent_1.batch_size) + ' steps')
    step = 0
    while len(xp_buffer_1) < agent_1.batch_size:
        actions = []
        for env in range(processes):
            actions.append(np.random.choice(range(0, num_actions_1)))
        next_states, rewards, dones, infos = environments_1.step(actions)
        if any(infos[i]['sanitised'] == True for i in range(processes)):
            # do the things with A2
            sanitised = [infos[i]['sanitised'] for i in range(processes)]
            environments_2.env_method('update_active_agents', sanitised)
            sanitised_states = environments_1.env_method('get_returned_payload')
            contexts         = environments_1.env_method('get_context')
            plain_states     = environments_1.env_method('get_plain_payload')
            tokens           = environments_1.env_method('get_token')
            escape_tag       = environments_1.env_method('get_escape_tag')[0]
            environments_1.env_method('save_session')
            environments_2.env_method('load_session')
            environments_2.env_method('update_vars', tokens, escape_tag)
            successful_bypass = [False for _ in range(processes)]
            for i in range(max_a2_episodes):
                environments_2.reset()
                a2_state = environments_2.env_method('update_state', sanitised_states, contexts, plain_states)
                a2_dones = [False for i in range(processes)]
                num_a2_actions = 0
                while num_a2_actions < max_a2_actions and all(a2_done == False for a2_done in a2_dones):
                    a2_actions = [np.random.choice(range(0, num_actions_2)) for i in range(processes)]
                    a2_next_states, a2_rewards, a2_dones, a2_infos = environments_2.step(a2_actions)
                    a2_next_states = [a2_next_states[i].unsqueeze(0) for i in range(a2_next_states.shape[0])]
                    for i in range(processes):
                        if not a2_dones[i]:
                            for j in range(len(xp_buffers_2)):
                                xp_buffers_2[j].add_transition((a2_state[i][0], a2_actions[i], float(a2_rewards[i]), a2_next_states[i][0], a2_dones[i]))
                        else:
                            successful_bypass[i] = True
                    a2_state = a2_next_states
                    num_a2_actions += 1
            if any(bypass == True for bypass in successful_bypass):
                #update state of A1
                new_states_encodings = environments_2.env_method('get_successful_instance')
                new_states = [new_states_encodings[process][0] for process in range(processes)]
                encoding = [new_states_encodings[process][1] for process in range(processes)]
                capitalisation = [new_states_encodings[process][2] for process in range(processes)]
                observations = environments_1.env_method('update_sanitisation_bypass', new_states, encoding, capitalisation, successful_bypass)
                for observation in observations:
                    environments_1.env_method('add_observation_to_states', observation)
            # change the reward to penalise if unable to bypass sanitisation
            for i in range(processes):
                if infos[i]['sanitised'] == True:
                    rewards[i] = rewards[i] + a2_rewards[i] if a2_rewards[i] < 0 else 2
        for i in range(processes):
            if not dones[i]:
                xp_buffer_1.add_transition((state[i], actions[i], float(rewards[i]), next_states[i], dones[i]))
            else:
                state = environments_1.reset()
        if step % 10 == 0:
            state = environments_1.reset()
        else:
            state = next_states
        step += 1
    environments_1.env_method('reset_payloads_found')



    add_to_buffer       = [True for _ in range(processes)]
    testing_length      = 99999 if not train else train_length
    correct_num_payloads = np.zeros((testing_length, processes), dtype=int)
    episode             = 0
    episode_rewards     = deque(maxlen=episode_length)
    num_eps_this_form   = 0

    total_episodes = []
    total_losses = []
    total_rewards = []
    total_mean_rewards = []
    total_ep_lengths = []

    source, sink = environments_1.env_method('get_source_sink')[0]
    injection_form = environments_1.env_method('get_injection_site')
    print('Source:' + source)
    print('Sink:' + sink)
    print('Tag: ' + injection_form[0])

    succesful_xss = []
    number_of_requests = []
    number_of_requests_this_form = 0
    requests_until_payload_found = []
    requests_until_payload_found_this_form = 0
    sub_requests_until_payload_found = []
    sub_requests_until_payload_found_this_form = 0

    while episode < testing_length:
        ep_loss = []
        a2_ep_reward = []
        a2_ep_loss = []
        episode_disc_rewards = 0
        if success_cond(correct_num_payloads, episode, num_eps_this_form , train, xss_range, min_xss):
            if train:
                agent_1.save_model(directory='HAXSS', filename='agent_1')
                for key in agent_2:
                    agent_2[key].save_model(directory='HAXSS/agent_2', filename='agent_2_' + str(key))
                env_1_states = environments_1.get_attr('states')
                env_2_states = environments_2.get_attr('sub_states')
                with open('saved_models/HAXSS/env_1_states.pkl', 'wb') as f:
                    pickle.dump(env_1_states, f, pickle.HIGHEST_PROTOCOL)
                with open('saved_models/HAXSS/env_2_states.pkl', 'wb') as f:
                    pickle.dump(env_2_states, f, pickle.HIGHEST_PROTOCOL)
                np.save('saved_models/HAXSS/training_data/total_loss', total_losses, True)
                np.save('saved_models/HAXSS/training_data/mean_reward', total_mean_rewards, True)
                np.save('saved_models/HAXSS/training_data/total_reward', total_rewards, True)
                np.save('saved_models/HAXSS/training_data/total_payloads', correct_num_payloads, True)
            number_of_requests.append(number_of_requests_this_form)
            requests_until_payload_found.append(requests_until_payload_found_this_form)
            sub_requests_until_payload_found.append(sub_requests_until_payload_found_this_form)
            number_of_requests_this_form = 0
            requests_until_payload_found_this_form = 0
            sub_requests_until_payload_found_this_form = 0
            print('Successful XSS')
            print('Source:' + source)
            print('Sink:' + sink)
            print('Tag: ' + injection_form[0])
            payload = environments_1.env_method('get_all_payloads_found')
            #print(payload)
            succesful_xss.append({'source':source,  'sink':sink, 'injection_from':injection_form[0], 'payload': payload})
            print('Anealing to new form...')
            injection_form = environments_1.env_method(method_name='change_injection_form')
            source, sink = environments_1.env_method('get_source_sink')[0]
            num_eps_this_form = 0
            environments_2.set_attr('failed_state_pairs', {})
            if injection_form[0] is not None:
                environments_1.env_method(method_name='reset_payloads_found')
                print('Changed to form ' + injection_form[0] + '...')
                source, sink = environments_1.env_method('get_source_sink')[0]
                print('Source:'+source)
                print('Sink:'+sink)
                print('Tag: ' + environments_1.env_method('get_injection_site')[0])

            else:
                print('Finished all forms...')
                episode = testing_length - 1
        elif fail_cond(max_episodes, episode, correct_num_payloads, num_eps_this_form, train, xss_range, min_xss):
            if train:
                agent_1.save_model(directory='HAXSS', filename='agent_1')
                for key in agent_2:
                    agent_2[key].save_model(directory='HAXSS/agent_2', filename='agent_2_' + str(key))
                env_1_states = environments_1.get_attr('states')
                env_2_states = environments_2.get_attr('sub_states')
                with open('saved_models/HAXSS/env_1_states.pkl', 'wb') as f:
                    pickle.dump(env_1_states, f, pickle.HIGHEST_PROTOCOL)
                with open('saved_models/HAXSS/env_2_states.pkl', 'wb') as f:
                    pickle.dump(env_2_states, f, pickle.HIGHEST_PROTOCOL)
                np.save('saved_models/HAXSS/training_data/total_loss', total_losses, True)
                np.save('saved_models/HAXSS/training_data/mean_reward', total_mean_rewards, True)
                np.save('saved_models/HAXSS/training_data/total_reward', total_rewards, True)
                np.save('saved_models/HAXSS/training_data/total_payloads', correct_num_payloads, True)
            number_of_requests.append(number_of_requests_this_form)
            requests_until_payload_found.append(requests_until_payload_found_this_form)
            sub_requests_until_payload_found.append(sub_requests_until_payload_found_this_form)
            num_eps_this_form = 0
            environments_2.set_attr('failed_state_pairs', {})
            number_of_requests_this_form = 0
            requests_until_payload_found_this_form = 0
            sub_requests_until_payload_found_this_form = 0
            print('Cannot beat form...')
            print('Source:' + source)
            print('Sink:' + sink)
            print('Tag: ' + injection_form[0])
            payloads = environments_1.env_method('get_all_payloads_found') 
            print(payloads)
            print('Anealing to new form...')
            if any(payload_list > 0 for payload_list in (payloads)):
                succesful_xss.append({'source':source,  'sink':sink, 'injection_from':injection_form[0], 'payload': payloads})
            injection_form = environments_1.env_method(method_name='change_injection_form')
            if injection_form[0] is not None:
                environments_1.env_method(method_name='reset_payloads_found')
                print('Changed to form ' + injection_form[0] + '...')
                source, sink = environments_1.env_method('get_source_sink')[0]
                print('Source:' + source)
                print('Sink:' + sink)
                print('Tag: '+environments_1.env_method('get_injection_site')[0])
            else:
                print('Finished all forms...')
                episode = testing_length - 1
        state = environments_1.reset()
        for step in range(episode_length):
            actions = []
            actions = agent_1.get_action(state)
            next_states, rewards, dones, infos = environments_1.step(actions)
            intrinsic_reward = agent_1.rnd.compute_intrinsic_reward(state)
            rewards += intrinsic_reward.clamp(-1.0, 1.0).item()
            reward_masked = []
            if any(infos[i]['sanitised'] == True for i in range(processes)):
                # do the things with A2
                sanitised = [infos[i]['sanitised'] and not dones[i] for i in range(processes)]
                environments_2.env_method('update_active_agents', sanitised)
                # a2_state = next_states
                tokens = environments_1.env_method('get_token')
                contexts = environments_1.env_method('get_context')
                escape_tag = environments_1.env_method('get_escape_tag')[0]
                plain_states = environments_1.env_method('get_plain_payload')
                sanitised_states = environments_1.env_method('get_returned_payload')
                environments_1.env_method('save_session')
                environments_2.env_method('load_session')
                environments_2.env_method('update_vars', tokens, escape_tag)
                successful_bypass = [False for _ in range(processes)]
                for a2_eps in range(max_a2_episodes):
                    num_a2_actions = 0
                    environments_2.reset()
                    a2_dones = [False for _ in range(processes)]
                    add_to_a2_buffer = [True for _ in range(processes)]
                    a2_state = environments_2.env_method('update_state', sanitised_states, contexts, plain_states)
                    a2_episode_disc_rewards = np.array([0 for _ in range(len(agent_2))])
                    while num_a2_actions < max_a2_actions and all(a2_done == False for a2_done in a2_dones):
                        a2_actions = [agent_2[int(action)].get_action(a2_state[list(actions).index(action)]) for action in actions]

                        number_of_requests_this_form += processes
                        try:
                            a2_next_states, a2_rewards, a2_dones, a2_infos = environments_2.step(a2_actions)
                        except:
                            current_states = environments_2.get_attr('plain_text_state')
                            encoding = environments_2.env_method('get_encoding')
                            tokens = environments_2.get_attr('token')
                            environments_2 = make_envs_as_vec(action_space=num_actions_2, seed=seed, gamma=gamma, processes=processes, sites=sites,
                                      env=XSSSanitisationEnv, login=login_details,
                                      context=environments_1.env_method('get_context')[0],
                                      parent_tag=environments_1.env_method('get_escape_tag')[0], input_tags=input_tags, urls=environments_1.env_method('get_internal_urls')[0],
                                      transition_tags=transition_tags, transitions=input_transitions, features=features, source=source, sink=sink)
                            environments_2.env_method('update_active_agents', sanitised)
                            environments_2.env_method('update_vars', tokens, escape_tag)
                            environments_2.env_method('set_encoding', encoding)
                            environments_2.env_method('set_plain_text_state', current_states)
                            with open('./saved_models/HAXSS/env_2_states.pkl', 'rb') as f:
                                sub_states = pickle.load(f)
                                environments_2.env_method('set_internal_states', sub_states)
                            a2_next_states, a2_rewards, a2_dones, a2_infos = environments_2.step(a2_actions)
                        a2_next_states = [a2_next_states[i].unsqueeze(0) for i in range(a2_next_states.shape[0])]
                        a2_rewards_masked = [0 for _ in range(len(agent_2))]
                        if len(xp_buffers_2[list(xp_buffers_2)[0]]) > agent_2_batch_size:
                            a2_minibatches = {int(i): xp_buffers_2[int(i)].sample(agent_2_batch_size) for i in actions}
                            a2_losses = [0 for _ in range(len(agent_2))]
                            for action in actions:
                                a2_losses[int(action)] = agent_2[int(action)].dqn.train_q_network(
                                    a2_minibatches[int(action)], False, False)
                            for i in range(processes):
                                if add_to_a2_buffer[i] and infos[i]['sanitised']:
                                    a2_rewards_masked[int(actions[i])] = (a2_rewards.detach().squeeze(-1).numpy()[i])
                                    xp_buffers_2[int(a2_actions[i])].add_transition(
                                        (a2_state[i][0], a2_actions[i], float(a2_rewards[i]), a2_next_states[i][0],
                                         a2_dones[i]))
                                    if 'requested' in a2_infos[i].keys() and a2_infos[i]['requested'] == True:
                                        sub_requests_until_payload_found_this_form += 1
                                if a2_dones[i] and sanitised[i]:
                                    successful_bypass[i] = True
                                    new_states_encodings = environments_2.env_method('get_successful_instance')
                                    add_to_a2_buffer[i] = False
                            a2_ep_loss.append(a2_losses)
                            a2_episode_disc_rewards = a2_rewards_masked + np.multiply(
                                np.array([gamma for _ in range(len(agent_2))]), a2_episode_disc_rewards)
                        else:
                            for i in range(processes):
                                if not a2_dones[i]:
                                    for j in range(len(xp_buffers_2)):
                                        xp_buffers_2[j].add_transition((a2_state[i][0], a2_actions[i],
                                                                        float(a2_rewards[i]), a2_next_states[i][0],
                                                                        a2_dones[i]))
                                else:
                                    add_to_a2_buffer[i] = False
                                    successful_bypass[i] = True
                                    new_states_encodings = environments_2.env_method('get_successful_instance')
                        a2_state = a2_next_states
                        num_a2_actions += 1
                    a2_ep_reward.append(a2_episode_disc_rewards)

                    if any(bypass == True for bypass in successful_bypass):
                        # update state of A1
                        new_states = [new_states_encodings[process][0] for process in range(processes)]
                        encoding = [new_states_encodings[process][1] for process in range(processes)]
                        capitalisation = [new_states_encodings[process][2] for process in range(processes)]
                        observations = environments_1.env_method('update_sanitisation_bypass', new_states, encoding,
                                                                 capitalisation, successful_bypass)
                        for observation in observations:
                            environments_1.env_method('add_observation_to_states', observation)
                    # change the reward to penalise if unable to bypass sanitisation
                    for i in range(processes):
                        if infos[i]['sanitised'] == True and not dones[i] or not a2_dones[i]:
                            rewards[i] = rewards[i] + a2_rewards[i] if a2_rewards[i] < 0 else rewards[i]

            for i in range(processes):
                if add_to_buffer[i]:
                    reward_masked.append(rewards.detach().squeeze(-1).numpy()[i])
                    xp_buffer_1.add_transition((state[i], actions[i], float(rewards[i]),
                                              next_states[i], dones[i]))
                    requests_until_payload_found_this_form += processes
                else:
                    reward_masked.append(np.nan)
                if dones[i]:
                    add_to_buffer[i] = False
            number_of_requests_this_form += processes
            episode_rewards.append(reward_masked)
            episode_disc_rewards = np.nanmean(reward_masked) + gamma * episode_disc_rewards
            minibatch = xp_buffer_1.sample(batch_size)
            agent_1.rnd.update(minibatch)
            loss = agent_1.dqn.train_q_network(minibatch, priority, agent_1.rnd)

            (loss, q_loss, rnd_loss), priorities = loss
            # update xp_bufer with the indicies and the priorities
            xp_buffer_1.update_priorities(minibatch[4], priorities)
            ep_loss.append(loss)
            state = next_states

        num_eps_this_form += 1
        payloads_this_ep = []
        for i in range(processes):
            if num_eps_this_form > 1:
                payloads_this_ep.append(1 + correct_num_payloads[episode - 1][i]
                                        if add_to_buffer[i] == False
                                        else correct_num_payloads[episode - 1][i])
            else:
                payloads_this_ep.append(1
                                        if add_to_buffer[i] == False else 0)

        add_to_buffer =[True for _ in range(processes)]
        correct_num_payloads[episode] = payloads_this_ep

        if episode % update_step == 0 and episode != 0:
            print('Updating Target Network...')
            agent_1.update_network()


        for i in range(len(rewards)):
            print(
                "{:<5}{:<6}{:>2}{:<15}{:>.3f}{:<15}{:>.3f}{:<22}{:>.3f} {:<.3f} {:> .3f} {:<.3f}{:<40}".format(
                    str(episode),
                    'AGENT: ', i + 1,
                    ' EP_LOSS_AV: ', float(np.nanmean(ep_loss) / (step + 1)) if ep_loss else 0,
                    ' EP_REWARD_MEAN: ',
                    float(np.nanmean([list(episode_rewards)[j][i] for j in range(len(episode_rewards))])),
                    ' REWARD MIN/MAX/MEAN/DISC: ',
                    float(min([list(episode_rewards)[j][i] for j in range(len(episode_rewards))])),
                    float(max([list(episode_rewards)[j][i] for j in range(len(episode_rewards))])),
                    float(np.nanmean([list(episode_rewards)[j][i] for j in range(len(episode_rewards))])),
                    float(episode_disc_rewards),
                               ' PAYLOADS GENERATED: ' + str(correct_num_payloads[episode][i])
                ))
        print('\n')
        total_losses.append(np.mean(ep_loss) / step if ep_loss else 0)
        total_episodes.append(episode)
        total_rewards.append(episode_disc_rewards)
        total_mean_rewards.append(np.nanmean(episode_rewards))
        total_ep_lengths.append(step)

        episode += 1

    hours, rem = divmod(time.time() - start_time, 3600)
    minutes, seconds = divmod(rem, 60)
    print('Total run time: ')
    print("{:0>2}:{:0>2}:{:05.2f}".format(int(hours), int(minutes), seconds))
    print('Vulnerabilities found: '+str(len(succesful_xss)))

    if train:
        agent_1.save_model(directory='HAXSS', filename='agent_1')
        for key in agent_2:
            agent_2[key].save_model(directory='HAXSS/agent_2', filename='agent_2_'+str(key))
        env_1_states = environments_1.get_attr('states')
        env_2_states = environments_2.get_attr('sub_states')
        with open('saved_models/HAXSS/env_1_states.pkl', 'wb') as f:
            pickle.dump(env_1_states, f, pickle.HIGHEST_PROTOCOL)
        with open('saved_models/HAXSS/env_2_states.pkl', 'wb') as f:
            pickle.dump(env_2_states, f, pickle.HIGHEST_PROTOCOL)
    environments_1.close()
    environments_2.close()
    with open('saved_models/HAXSS/payloads_'+str(time.time())+'.pkl', 'wb') as f:
        pickle.dump(succesful_xss, f, pickle.HIGHEST_PROTOCOL)
    for xss in succesful_xss:
        print(xss)

    total_episodes[-1] = total_episodes[-2]
    plt.plot(total_episodes, total_mean_rewards, color='orange')
    plt.title('Mean reward of all agents in the episode')
    plt.xlabel('Episode')
    plt.ylabel('Reward')
    plt.grid()
    plt.savefig('./saved_models/HAXSS/rewards.png')
    #plt.show()


    plt.plot(total_episodes, total_losses)
    plt.title('Total Loss of Q-Network and RND')
    plt.xlabel('Episode')
    plt.ylabel('Loss')
    plt.grid()
    plt.savefig('./saved_models/HAXSS/loss.png')
    #plt.show()

    correct_num_payloads = correct_num_payloads[:len(total_episodes)]
    plt.plot(total_episodes, list(np.sum(correct_num_payloads.T, axis=0)), linewidth=2)
    plt.xlabel('Episode')
    plt.ylabel('Successful XSS generated')
    plt.grid()
    plt.savefig('./saved_models/HAXSS/payloads.eps', format='eps')
    #plt.show()

    if train:
        np.save('saved_models/HAXSS/training_data/total_loss', total_losses, True)
        np.save('saved_models/HAXSS/training_data/mean_reward', total_mean_rewards, True)
        np.save('saved_models/HAXSS/training_data/total_reward', total_rewards, True)
        np.save('saved_models/HAXSS/training_data/total_payloads', correct_num_payloads, True)
    else:
        np.save('saved_models/HAXSS/testing_data/total_loss', total_losses, True)
        np.save('saved_models/HAXSS/testing_data/mean_reward', total_mean_rewards, True)
        np.save('saved_models/HAXSS/testing_data/total_reward', total_rewards, True)
        np.save('saved_models/HAXSS/testing_data/total_payloads', correct_num_payloads, True)