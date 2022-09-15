import torch

class Categorical(torch.nn.Module):
    def __init__(self, input_dimension, output_dimension):
        super(Categorical, self).__init__()

        init_ = lambda m: init(m, torch.nn.init.orthogonal_, lambda x: torch.nn.init.constant_(x, 0), gain=0.01)

        self.linear = init_(torch.nn.Linear(input_dimension, output_dimension))

    def forward(self, input):
        output = self.linear(input)
        return FixedCategorical(logits=output)

class FixedCategorical(torch.distributions.Categorical):
    def sample(self):
        return super().sample().unsqueeze(-1)

    def log_probs(self, actions):
        return (super().log_prob(actions.squeeze(-1)).view(actions.size(0), -1).sum(-1).unsqueeze(-1))

    def mode(self):
        return self.probs.argmax(dim=-1, keepdim=True)


def init(module, weight_init, bias_init, gain=1):
    weight_init(module.weight.data, gain=gain)
    bias_init(module.bias.data)
    return module

