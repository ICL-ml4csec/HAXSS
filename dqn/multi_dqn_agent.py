from dqn.distributions import Categorical
from dqn.dqn import DQN, DuelingDQN, AverageDQN
from curiosity.rnd import *
import torch
import os


# The Agent class allows the agent to interact with the environment.
class Agent:

    # The class initialisation function.
    def __init__(self, num_actions, epsilon = 1.0, batch_size=32, gamma=0.9,
                 lr=0.0001, model='dqn', rnd=False, processes=1,
                 eps=0.001, alpha=0.99, input_dimension=2):
        # set epsilon
        self.epsilon = epsilon
        self.batch_size = batch_size
        self.num_actions = num_actions
        # curiosity using the RND model
        if rnd:
            self.rnd        = RNDAgentDqn(batch_size, input_dimension=2)
            self.reward_rms = RunningMeanStd()
        else:
            self.rnd = None
        if model == 'dqn' and self.rnd:
            # initalise the Q-Network
            self.model_type = 'dqn'
            self.dqn = DQN(gamma=gamma, lr=lr, batch_size=batch_size,
                           rnd_params=self.rnd.rnd_predictor.parameters(), input_dimension=input_dimension,output_dimension=64)
            self.dist = Categorical(64, self.num_actions)
        elif model == 'dqn':
            # initalise the Q-Network
            self.model_type = 'dqn'
            self.dqn = DQN(gamma=gamma, lr=lr, batch_size=batch_size, output_dimension=64, input_dimension=input_dimension)
            self.dist = Categorical(64, self.num_actions)
        elif model == 'dueling':
            self.model_type = 'dueling_dqn'
            self.dqn = DuelingDQN(batch_size=batch_size,lr=lr, input_dimension=input_dimension, output_dimension=self.num_actions, gamma=gamma)
        elif model == 'average':
            self.model_type = 'average_dqn'
            self.dqn = AverageDQN(batch_size=batch_size, lr=lr, input_dimension=input_dimension, output_dimension=self.num_actions, gamma=gamma)

    def save_model(self, directory='multi_dqn', filename='dqn'):
        path = os.path.abspath(os.getcwd())
        if not os.path.exists(path + '/saved_models'):
            os.mkdir(path + '/saved_models')
        if not os.path.exists(path + '/saved_models/'+directory):
                os.makedirs(path + '/saved_models/'+directory)
        model_to_save = {'dqn_q_net_state_dict': self.dqn.q_network.state_dict(),
                         'dqn_target_state_dict': self.dqn.target_network.state_dict(),
                         'opt_state_dict': self.dqn.optimiser.state_dict()}
        if self.rnd:
            model_to_save['rnd_state_dict'] = self.rnd.rnd_predictor.state_dict()
        torch.save(model_to_save, path + '/saved_models/'+directory+'/'+filename+'.pt')

    def load_model(self, relative_path='./saved_models/multi_dqn/dqn.pt'):
        if self.model_type == 'dqn':
            path = os.path.abspath(os.getcwd())
            check_point = torch.load(relative_path)
            self.dqn.q_network.load_state_dict(check_point['dqn_q_net_state_dict'])
            self.dqn.target_network.load_state_dict(check_point['dqn_target_state_dict'])
            self.dqn.optimiser.load_state_dict(check_point['opt_state_dict'])
            if self.rnd:
                self.rnd.rnd_predictor.load_state_dict(check_point['rnd_state_dict'])
                self.rnd.rnd_predictor.train()
            self.dqn.q_network.train()
            self.dqn.target_network.train()
        else:
            print('Saving model type: '+self.model_type+ ' is not supported')

    def update_network(self):
        self.dqn.update_target_network()


    def update_epsilon(self):
        if self.epsilon > 0.1:
            self.epsilon *= 0.999
        else:
            self.epsilon = 0.1
        return

    def get_action(self, state):
        if np.random.uniform(0, 1) < self.epsilon:
            action = torch.tensor([[np.random.choice(range(0, self.num_actions))] for _ in range(len(state))])
            dist_entropy = None
        else:
            state_q_values = torch.tensor(self.dqn.predict_q_values(state))
            if self.model_type == 'dqn':
                dist = self.dist(state_q_values)
                action = dist.sample().squeeze(0)
                dist_entropy = dist.entropy().mean()
            else:
                action = np.argmax(state_q_values).unsqueeze(0).unsqueeze(0)

        return action



