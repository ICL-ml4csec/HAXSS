

class Config:
    def __init__(self, config_dict=None):
        self.gamma                      = config_dict['gamma']
        self.epsilon                    = config_dict['epsilon']
        self.batch_size                 = config_dict['batch_size']
        self.update_step                = config_dict['update_step']
        self.episode_length             = config_dict['episode_length']
        self.reward_correct             = config_dict['reward_correct']
        self.reward_reflect             = config_dict['reward_reflect']
        self.reward_partial             = config_dict['reward_partial']
        self.learning_rate              = config_dict['learning_rate']
        self.training_time              = config_dict['training_time']
        self.priority                   = config_dict['priority']
        self.complete_random_pretrain   = config_dict['complete_random_pretrain']
        self.exploring_steps            = config_dict['exploring_steps']

