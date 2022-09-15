import collections
import numpy as np


class PriorityReplayBuffer:
    def __init__(self, max_capacity=5000, alpha=0.6):
        self.buffer = collections.deque(maxlen=max_capacity)
        self.alpha = alpha
        self.capacity = max_capacity
        self.priorities = np.zeros((max_capacity,), dtype=np.float32)

    def add_transition(self, transition):
        max_priority = self.priorities.max() if self.buffer else 1.0
        self.buffer.append(transition)
        self.priorities[len(self.buffer) - 1] = max_priority


    def sample(self, batch_size, beta=0.4):
        priorities = self.priorities[:len(self.buffer)]
        sample_prob = (priorities ** self.alpha) / (priorities ** self.alpha).sum()

        buffer_indices = np.random.choice(len(self.buffer), size=batch_size, p=sample_prob, replace=False)
        transition_list = [self.buffer[index] for index in buffer_indices]

        weights = (len(self.buffer) * sample_prob[buffer_indices]) ** -beta
        weights /= weights.max()

        states, actions, rewards, next_states, dones = zip(*transition_list)
        return states, actions, rewards, next_states, buffer_indices, weights, dones


    def update_priorities(self, batch_indices, batch_priorities):
        for index, priority in zip(batch_indices, batch_priorities):
            self.priorities[index] = priority

    def __len__(self):
        return len(self.buffer)


class ReplayBuffer:
    def __init__(self, max_capacity=5000):
        self.buffer = collections.deque(maxlen=max_capacity)

    def add_transition(self, transition):
        self.buffer.append(transition)

    def sample(self, batch_size):
        buffer_indices = np.random.choice(len(self.buffer), batch_size, replace=False)
        transition_list = [self.buffer[index] for index in buffer_indices]
        states, actions, rewards, next_states, dones = zip(*transition_list)
        return states, actions, rewards, next_states, dones

    def __len__(self):
        return len(self.buffer)
