
from stable_baselines3.common.vec_env.vec_normalize import VecNormalize as VecNormalise_
from stable_baselines3.common.vec_env import (DummyVecEnv, SubprocVecEnv, VecEnvWrapper)
import torch
import gym
import numpy as np

def list_to_tensor(list):
    return torch.stack(list)

def make_env(rank, sites, update_obs,string_seed, action_space, environ,
             urls=None,input_tags=None, transitions=None, seed=0, login=None, features=None,
             transition_tags=None, context=None, parent_tag=None, sink=None, source=None):
    def _thunk():
        environment = environ
        if input_tags is None and transitions is None and context is None:
            env = environment(action_space, 1, sites=sites, string_seed=string_seed, update_obs=update_obs)
        elif context or source:
            env = environment(action_space, update_obs=update_obs, string_seed=string_seed, context=context, rank=rank,
                              parent_tag=parent_tag,  transition_tags=transition_tags, transitions=transitions, sites=sites, urls=urls, source=source, sink=sink, features=features, input_tags=input_tags)
        else:
            env = environment(action_space, sites=sites, update_obs=update_obs, string_seed=string_seed, urls=urls,
                              input_tags=input_tags, transitions=transitions, login=login, features=features, transition_tags=transition_tags, rank=rank)


        env.seed(seed+rank)
        return env
    return _thunk()


def make_envs_as_vec(seed, processes, gamma, sites, env, action_space, urls=None, input_tags=None, 
                     transitions=None, login=None, features=None, transition_tags=None,
                     context=None, parent_tag=None, sink=None, source=None):
    if processes > 1:
        envs = SubprocVecEnv([lambda: make_env(parent_tag=parent_tag,context=context, action_space=action_space,rank=i, sites=sites, environ=env, string_seed=seed, urls=urls,input_tags=input_tags, transitions=transitions, login=login, features=features, transition_tags=transition_tags, update_obs=False, source=source, sink=sink) for i in range(processes)],
                             start_method='spawn')
    else:
        envs = DummyVecEnv([lambda: make_env(parent_tag=parent_tag,context=context, action_space=action_space, rank=0, sites=sites, environ=env,string_seed=seed,urls=urls, input_tags=input_tags, transitions=transitions, login=login, features=features, transition_tags=transition_tags, update_obs=True, source=source, sink=sink)])


    if len(envs.observation_space.shape) == 1:
        envs = VecNormalise(envs, gamma=gamma)
    if processes > 1:
        envs = VecPyTorch(envs)
        for i in range(processes):
            envs.set_attr('rank', i, i)

    else:
        envs = VecPyTorchSingle(envs)

    return envs

class StepLimitMask(gym.Wrapper):
    def step(self, action):
        observation, reward, done, info = self.env.step(action)
        if done and self.env._max_episode_steps == self.env._elapsed_steps:
            info['bad_transition'] = True
        return observation, reward, done, info

    def reset(self, **kwargs):
        return self.env.reset(**kwargs)

class VecPyTorch(VecEnvWrapper):
    def __init__(self, venv):
        super(VecPyTorch, self).__init__(venv)

    def reset(self):
        observation = self.venv.reset()
        observation_decoded = np.ndarray(observation.shape)

        for x in range(observation.shape[0]):
            for y in range(observation.shape[1] - 1):
                observation_decoded[x][y] = \
                   self.venv.env_method('add_observation_to_states',
                                         observation[x][y])[0]
            observation_decoded[x][-1] = observation[x][-1]
        observation_decoded = torch.from_numpy(observation_decoded).float()
        return observation_decoded

    def step_async(self, actions):
        if isinstance(actions, torch.LongTensor):
            actions = actions.squeeze(1)
        #actions = actions.numpy()
        try:
            self.venv.step_async(actions)
        except RuntimeError as e:
            self.venv.step_async(actions)

    def step_wait(self):
        observations, reward, done, info = self.venv.step_wait()
        #observations = observations[:,0]
        observations_decoded = np.ndarray(observations.shape)
        for x in range(observations.shape[0]):
            if np.count_nonzero(observations[x] == observations[x][0]) != len(observations[x]):
                for y in range(observations.shape[1]):
                    new_obs = self.venv.env_method('add_observation_to_states',
                                                 observations[x][y])[0]
                    if type(new_obs) != int:
                        while type(new_obs) != int:
                            new_obs = self.venv.env_method('add_observation_to_states',
                                                           observations[x][y])[0]
                    observations_decoded[x][y] = new_obs
            else:
                new_obs = self.venv.env_method('add_observation_to_states',
                                         observations[x][0])[0]
                if type(new_obs) != int:
                    while type(new_obs) != int:
                        new_obs = self.venv.env_method('add_observation_to_states',
                                                       observations[x][0])[0]
                observations_decoded[x][0] =  observations_decoded[x][1] = new_obs

        observations_decoded = torch.from_numpy(observations_decoded).float()
        reward = torch.from_numpy(reward).unsqueeze(dim=1).float()
        return observations_decoded, reward, done, info


class VecBasePyTorch(VecEnvWrapper):
    def __init__(self, venv):
        super(VecBasePyTorch, self).__init__(venv)
    def reset(self):
        observation = self.venv.reset()
        #observation = observation[0]
        observation_decoded = np.ndarray(observation.shape)

        for x in range(observation.shape[0]):
            if np.count_nonzero(observation[x] == observation[x][0]) != len(observation[x]):
                for y in range(observation.shape[1]):
                    observation_decoded[x][y] = \
                       self.venv.env_method('add_observation_to_states',
                                             observation[x][y])[0]
            else:
                observation_decoded[x][0] =  observation_decoded[x][1] = \
                       self.venv.env_method('add_observation_to_states',
                                         observation[x][0])[0]
        observation = torch.from_numpy(observation).float()
        return observation

    def step_async(self, actions):
        if isinstance(actions, torch.LongTensor):
            actions = actions.squeeze(1)
        #actions = actions.numpy()
        self.venv.step_async(actions)

    def step_wait(self):
        observations, reward, done, info = self.venv.step_wait()
        #observations = observations[0]
        observations_decoded = np.ndarray(observations.shape)

        for x in range(observations.shape[0]):
            if np.count_nonzero(observations[x] == observations[x][0]) != len(observations[x]):
                for y in range(observations.shape[1]):
                    observations_decoded[x][y] = \
                       self.venv.env_method('add_observation_to_states',
                                             observations[x][y])[0]
            else:
                observations_decoded[x][0] =  observations_decoded[x][1] = \
                       self.venv.env_method('add_observation_to_states',
                                         observations[x][0])[0]

        observations_decoded = torch.from_numpy(observations_decoded).float()
        reward = torch.from_numpy(reward).unsqueeze(dim=1).float()
        return observations_decoded, reward, done, info




class VecPyTorchSingle(VecEnvWrapper):
    def __init__(self, venv):
        super(VecPyTorchSingle, self).__init__(venv)

    def reset(self):
        observation = self.venv.reset()[0]
        observation = torch.from_numpy(observation).float()
        return observation

    def step_async(self, actions):
        if isinstance(actions, torch.LongTensor):
            actions = actions.squeeze(1)
        self.venv.step_async(actions)

    def step_wait(self):
        observations, reward, done, info = self.venv.step_wait()
        observations = observations[0]
        observations = torch.from_numpy(observations).float()
        reward = torch.from_numpy(reward).unsqueeze(dim=1).float()
        return observations, reward, done, info

class VecNormalise(VecNormalise_):
    def __init__(self, *args, **kwargs):
        super(VecNormalise, self).__init__(*args, **kwargs)
        self.training = True

    def _obfilt(self, obs, update=True):
        if self.obs_rms:
            if self.training and update:
                self.obs_rms.update(obs)
            obs = np.clip((obs - self.obs_rms.mean) / np.sqrt(self.obs_rms.var + self.epsilon),
                          -self.clipob, self.clipob)
            return obs
        else:
            return obs

    def train(self):
        self.training = True

    def eval(self):
        self.training = False
