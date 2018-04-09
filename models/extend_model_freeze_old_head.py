import sonnet as snt
import tensorflow as tf
import numpy as np

from models.extend_model import ExtendModel
import models.layers as Layers
from constants import Constants

class ExtendModelFreezeOldHead(ExtendModel):
  '''
  The model name and the build function must be the same (in terms of what tensorflow sees and name scopes)
  '''
  def __init__(self, name='StandardModel'):
    super().__init__(name=name)

  def prepare_for_training(self, sess, graph_nodes):
    '''
    Adds weights/biases to the output layer so its number of outputs matches source num_way + target num_way
    and replaces 'outputs' in `graph_nodes`
    Also replaces graph_nodes['train_op'] with some frozen weights
    '''
    ##### EXTEND LAYER #####
    # Get the current weight values
    weights_tf, biases_tf = self._output_layer.get_variables()
    weights, biases = sess.run([weights_tf, biases_tf])
    # Compute number of new weights to be added
    num_new_outputs = Constants.config['target_num_way'] - biases.shape[0]

    # Create, connect and initialise the new layer
    new_layer = snt.Linear(num_new_outputs, name='class_linear2')
    new_layer_outputs = new_layer(self._output_layer_inputs)
    sess.run(tf.variables_initializer(new_layer.get_variables()))
    self._output_layer_outputs = tf.concat([self._output_layer_outputs, new_layer_outputs], -1)

    # Get all (gradient, weight) pairs
    grads = graph_nodes['optimizer'].compute_gradients(graph_nodes['loss'])
    # keep all gradients except for the old softmax head
    allowed_gradients = [(grad, weight) for (grad, weight) in grads if weight not in self._output_layer.get_variables()]
    # Replace the train op with our limited update
    graph_nodes['train_op'] = graph_nodes['optimizer'].apply_gradients(allowed_gradients, global_step=graph_nodes['global_step'])

    # Initialise the variables created by the optimizer
    leftover_strings = set([v.decode('UTF-8') for v in sess.run(tf.report_uninitialized_variables())])
    leftover_vars = [v for v in tf.global_variables() if v.name.split(':')[0] in leftover_strings]
    sess.run(tf.variables_initializer(leftover_vars))
