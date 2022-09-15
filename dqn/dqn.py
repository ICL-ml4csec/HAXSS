import torch

class StreamLayer(torch.nn.Module):
    def __init__(self, input_dimension=128, output_dimension=1):
        super(StreamLayer, self).__init__()
        self.layer_1 = torch.nn.Linear(in_features=input_dimension, out_features=128)
        self.layer_2 = torch.nn.Linear(in_features=128, out_features=output_dimension)

    def forward(self, input):
        layer_1_output = torch.nn.functional.relu(self.layer_1(input))
        output = torch.nn.functional.relu(self.layer_2(layer_1_output))
        return output

# The NeuralNetwork class inherits the torch.nn.Module class, which represents a neural network.
class NeuralNetwork(torch.nn.Module):

    # The class initialisation function. This takes as arguments the dimension of the network's input (i.e. the dimension of the state), and the dimension of the network's output (i.e. the dimension of the action).
    def __init__(self, input_dimension, output_dimension):
        # Call the initialisation function of the parent class.
        super(NeuralNetwork, self).__init__()
        # Define the network layers.
        self.layer_1 = torch.nn.Linear(in_features=input_dimension, out_features=64)
        #torch.nn.init.xavier_normal_(self.layer_1.weight)
        self.layer_2 = torch.nn.Linear(in_features=64, out_features=96)
        #torch.nn.init.xavier_normal_(self.layer_2.weight)
        self.layer_3 = torch.nn.Linear(in_features=96, out_features=64)
        #self.layer_4 = torch.nn.Linear(in_features=228, out_features=114)
        self.output_layer = torch.nn.Linear(in_features=64, out_features=output_dimension)
        #torch.nn.init.xavier_normal_(self.output_layer.weight)


    # Function which sends some input data through the network and returns the network's output. In this example, a ReLU activation function is used for both hidden layers, but the output layer has no activation function (it is just a linear layer).
    def forward(self, input):
        layer_1_output = torch.tanh(self.layer_1(input))
        layer_2_output = torch.tanh(self.layer_2(layer_1_output))
        layer_3_output = torch.tanh(self.layer_3(layer_2_output))
        #layer_4_output = torch.nn.functional.relu(self.layer_4(layer_3_output))
        output = self.output_layer(layer_3_output)
        return output



# The DQN class
class DQN:

    # class initialisation function.
    #output = 42500 for the sliced vector action space
    def __init__(self, input_dimension=1, output_dimension=24, gamma=0.9, lr=0.0001,
                 batch_size=32, rnd_params=None):
        if torch.cuda.is_available():
            dev = 'cuda:0'
        else:
            dev = 'cpu'
        self.device = torch.device(dev)
        self.input_dimension = input_dimension
        # Create a Q-network, which predicts the q-value for a particular state.
        self.q_network = NeuralNetwork(input_dimension=input_dimension, output_dimension=output_dimension).to(self.device)
        self.target_network = NeuralNetwork(input_dimension=input_dimension, output_dimension=output_dimension).to(self.device)
        self.update_target_network()
        # optimiser used when updating the Q-network.
        # learning rate determines how big each gradient step is during backpropagation.
        if rnd_params:
            params = list(self.q_network.parameters()) + list(rnd_params)
        else:
            params = self.q_network.parameters()
        self.optimiser = torch.optim.Adam(params, lr=lr)
        self.gamma = gamma
        self.batch_size = batch_size



    # Function to train the Q-network
    def train_q_network(self, minibatch, priority, rnd, entropy=None):
        # Set all the gradients stored in the optimiser to zero.
        self.optimiser.zero_grad()
        # Calculate the loss for this transition.
        loss = self._calculate_loss(minibatch, priority)
        if priority:
            updated_priorities = loss + 1e-5
            loss = loss.mean()
            rnd_loss = None
        if entropy:
            loss -= entropy * 0.01
        q_loss = loss
        if rnd:
            rnd_loss = rnd.calculate_loss(minibatch)
            loss += rnd_loss
        # Compute the gradients based on this loss, i.e. the gradients of the loss with respect to the Q-network parameters.
        loss.backward()
        # Take one gradient step to update the Q-network.
        self.optimiser.step()
        # Return the loss as a scalar
        if priority:
            return (loss.item(), q_loss.item(), rnd_loss.item()), updated_priorities
        else:
            return loss.item()

    # Function to calculate the loss for a minibatch.
    def _calculate_loss(self, minibatch, priority):
        if priority:
            states, actions, rewards, next_states, buffer_indices, weights, dones = minibatch
            weight_tensor = torch.tensor(weights, dtype=torch.float32).to(self.device)
        else:
            states, actions, rewards, next_states, dones = minibatch
        state_tensor = torch.cat(states)
        state_tensor = torch.reshape(state_tensor, (self.batch_size, self.input_dimension)).to(self.device)
        action_tensor = torch.tensor(actions, dtype=torch.int64).to(self.device)
        reward_tensor = torch.tensor(rewards, dtype=torch.float32).to(self.device)
        next_state_tensor = torch.cat(next_states)
        next_state_tensor = torch.reshape(next_state_tensor, (self.batch_size, self.input_dimension)).to(self.device)
        done_tensor = torch.tensor(dones, dtype=torch.int32).to(self.device)
        # Calculate the predicted q-values for the current state
        state_q_values = self.q_network.forward(state_tensor)
        state_action_q_values = state_q_values.gather(dim=1, index=action_tensor.unsqueeze(-1)).squeeze(-1)
        # Get the q-values for then next state
        next_state_q_values = self.target_network.forward(next_state_tensor).detach()  # Use .detach(), so that the target network is not updated
        # Get the maximum q-value
        next_state_max_q_values = next_state_q_values.max(1)[0]
        # Calculate the target q values
        target_state_action_q_values = reward_tensor + self.gamma * next_state_max_q_values * (1 - done_tensor)
        # Calculate the loss between the current estimates, and the target Q-values
        loss = torch.nn.MSELoss()(state_action_q_values, target_state_action_q_values)
        if priority:
            loss = loss * weight_tensor
        # Return the loss
        del state_tensor

        return loss

    def predict_q_values(self, state):
        if type(state) != torch.Tensor:
            state_tensor = torch.tensor(state, dtype=torch.float32).unsqueeze(0).to(self.device)
        else:
            state_tensor = state.clone().detach().unsqueeze(0).type(torch.float32).to(self.device)
        predicted_q_value_tensor = self.q_network.forward(state_tensor)
        return predicted_q_value_tensor.data.cpu().numpy()

    def update_target_network(self):
        self.target_network.load_state_dict(self.q_network.state_dict())

class DuelingDQN:
    def __init__(self, input_dimension=1, output_dimension=24, gamma=0.9, lr=0.0001, batch_size=32):
        if torch.cuda.is_available():
            dev = 'cuda:0'
        else:
            dev = 'cpu'
        self.device = torch.device(dev)
        self.q_network            = NeuralNetwork(input_dimension=input_dimension, output_dimension=128)
        self.q_value_layer        = StreamLayer(input_dimension=128)
        self.q_advantage_layer    = StreamLayer(output_dimension=output_dimension)
        self.input_dimension      = input_dimension
        self.target_network       = NeuralNetwork(input_dimension=input_dimension, output_dimension=128)
        self.target_value_layer        = StreamLayer(input_dimension=128)
        self.target_advantage_layer    = StreamLayer(output_dimension=output_dimension)
        self.update_target_network()

        parameters = list(self.q_network.parameters()) + \
                     list(self.q_value_layer.parameters()) +\
                     list(self.q_advantage_layer.parameters())
        self.optimiser          = torch.optim.Adam(parameters, lr=lr)
        self.batch_size         = batch_size
        self.gamma              = gamma

    def forward_q(self, input):
        features = self.q_network.forward(input)
        values = self.q_value_layer.forward(features)
        advantages = self.q_advantage_layer.forward(features)
        return values + (advantages - advantages.mean())

    def forward_target(self, input):
        features = self.target_network.forward(input)
        values = self.target_value_layer.forward(features)
        advantages = self.target_advantage_layer.forward(features)
        return values + (advantages - advantages.mean())

    # Function to train the Q-network
    def train_q_network(self, minibatch, priority, rnd):
        # Set all the gradients stored in the optimiser to zero.
        self.optimiser.zero_grad()
        # Calculate the loss for this transition.
        loss = self._calculate_loss(minibatch, priority)
        if priority:
            updated_priorities = loss + 1e-5
            loss = loss.mean()
        # Compute the gradients based on this loss, i.e. the gradients of the loss with respect to the Q-network parameters.
        loss.backward()
        # Take one gradient step to update the Q-network.
        self.optimiser.step()
        # Return the loss as a scalar
        if priority:
            return loss.item(), updated_priorities
        else:
            return loss.item()

    def _calculate_loss(self, minibatch, priority):
        if priority:
            states, actions, rewards, next_states, buffer_indices, weights, dones = minibatch
            weight_tensor = torch.tensor(weights, dtype=torch.float32)
        else:
            states, actions, rewards, next_states, dones = minibatch
        state_tensor = torch.cat(states)
        state_tensor = torch.reshape(state_tensor, (self.batch_size, self.input_dimension)).to(self.device)
        action_tensor = torch.tensor(actions, dtype=torch.int64).to(self.device)
        reward_tensor = torch.tensor(rewards, dtype=torch.float32).to(self.device)
        next_state_tensor = torch.cat(next_states)
        next_state_tensor = torch.reshape(next_state_tensor, (self.batch_size, self.input_dimension)).to(self.device)
        done_tensor = torch.tensor(dones, dtype=torch.int32).to(self.device)

        state_q_values = self.forward_q(state_tensor)
        state_action_q_values = state_q_values.gather(dim=1, index=action_tensor.unsqueeze(-1)).squeeze(-1)

        next_state_q_values = self.forward_target(next_state_tensor).detach()  # Use .detach(), so that the target network is not updated
        next_state_max_q_values = next_state_q_values.max(1)[0]

        target_state_action_q_values = reward_tensor + self.gamma * next_state_max_q_values * (1 - done_tensor)

        loss = torch.nn.MSELoss()(state_action_q_values, target_state_action_q_values)
        if priority:
            loss = loss * weight_tensor
        # Return the loss
        return loss

    def predict_q_values(self, state):
        state_tensor = torch.tensor(state, dtype=torch.float32).unsqueeze(0)
        predicted_q_value_tensor = self.forward_q(state_tensor)
        return predicted_q_value_tensor.data.cpu().numpy()

    def update_target_network(self):
        self.target_network.load_state_dict(self.q_network.state_dict())
        self.target_value_layer.load_state_dict(self.q_value_layer.state_dict())
        self.target_advantage_layer.load_state_dict(self.q_advantage_layer.state_dict())


class AverageDQN:
    # class initialisation function.
    def __init__(self, input_dimension=1, output_dimension=24, gamma=0.9, lr=0.0001, batch_size=32,
                 rnd_params=None, num_target_q=10):
        if torch.cuda.is_available():
            dev = 'cuda:0'
        else:
            dev = 'cpu'
        self.device = torch.device(dev)
        # Create a Q-network, which predicts the q-value for a particular state.
        self.q_network = NeuralNetwork(input_dimension=input_dimension, output_dimension=output_dimension)
        self.target_q_values = {}
        self.num_target_vals = num_target_q
        for i in range(num_target_q):
            self.target_q_values[i] = NeuralNetwork(input_dimension=input_dimension, output_dimension=output_dimension)
        self.num_active = 0
        self.output_dimension = output_dimension
        self.update_target_network()
        self.input_dimension = input_dimension
        # optimiser used when updating the Q-network.
        # learning rate determines how big each gradient step is during backpropagation.
        if rnd_params:
            params = list(self.q_network.parameters()) + list(rnd_params)
        else:
            params = self.q_network.parameters()
        self.optimiser = torch.optim.Adam(params, lr=lr)
        self.gamma = gamma
        self.batch_size = batch_size
        # stuff for testing
        self.q_values = []

    # Function to train the Q-network
    def train_q_network(self, minibatch, priority, rnd):
        # Set all the gradients stored in the optimiser to zero.
        self.optimiser.zero_grad()
        # Calculate the loss for this transition.
        loss = self._calculate_loss(minibatch, priority)
        if priority:
            updated_priorities = loss + 1e-5
            loss = loss.mean()
        if rnd:
             loss += rnd.calculate_loss(minibatch)
        # Compute the gradients based on this loss, i.e. the gradients of the loss with respect to the Q-network parameters.
        loss.backward()
        # Take one gradient step to update the Q-network.
        self.optimiser.step()
        # Return the loss as a scalar
        if priority:
            return loss.item(), updated_priorities
        else:
            return loss.item()



    # Function to calculate the loss for a minibatch.
    def _calculate_loss(self, minibatch, priority):
        if priority:
            states, actions, rewards, next_states, buffer_indices, weights, dones = minibatch
            weight_tensor = torch.tensor(weights, dtype=torch.float32)
        else:
            states, actions, rewards, next_states, dones = minibatch
        state_tensor = torch.cat(states)
        state_tensor = torch.reshape(state_tensor, (self.batch_size, self.input_dimension)).to(self.device)
        action_tensor = torch.tensor(actions, dtype=torch.int64).to(self.device)
        reward_tensor = torch.tensor(rewards, dtype=torch.float32).to(self.device)
        next_state_tensor = torch.cat(next_states)
        next_state_tensor = torch.reshape(next_state_tensor, (self.batch_size, self.input_dimension)).to(self.device)
        done_tensor = torch.tensor(dones, dtype=torch.int32).to(self.device)
        # Calculate the predicted q-values for the current state
        state_q_values = self.q_network.forward(state_tensor)
        state_action_q_values = state_q_values.gather(dim=1, index=action_tensor.unsqueeze(-1)).squeeze(-1)
        # Get the q-values for then next state
        next_state_q_values = torch.FloatTensor(self.batch_size, self.output_dimension).zero_()
        for i in range(self.num_active):
            next_state_q_values = torch.add(next_state_q_values, self.target_q_values[i](next_state_tensor).detach())
        # Get the maximum q-value
        next_state_max_q_values = next_state_q_values.max(1)[0]
        # Calculate the target q values
        target_state_action_q_values = reward_tensor + self.gamma/self.num_active * next_state_max_q_values * (1 - done_tensor)
        # Calculate the loss between the current estimates, and the target Q-values
        loss = torch.nn.MSELoss()(state_action_q_values, target_state_action_q_values)
        if priority:
            loss = loss * weight_tensor
        # Return the loss
        return loss

    def predict_q_values(self, state):
        state_tensor = torch.tensor(state, dtype=torch.float32).unsqueeze(0)
        predicted_q_value_tensor = self.q_network.forward(state_tensor)
        return predicted_q_value_tensor.data.numpy()

    def update_target_network(self):
        self.num_active += 1
        if self.num_active > self.num_target_vals:
            self.num_active = self.num_target_vals
        for i in range(self.num_active-1, 0, -1):
            self.target_q_values[i].load_state_dict(self.target_q_values[i-1].state_dict())
        self.target_q_values[0].load_state_dict(self.q_network.state_dict())