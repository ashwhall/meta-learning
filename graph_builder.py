import importlib
import os.path
import importlib
import tensorflow as tf

from optimizer import Optimizer
from helper import Helper
from constants import Constants

SOURCE_TRAIN_SUMMARIES = 'source_train_summaries'
SOURCE_TEST_SUMMARIES = 'source_test_summaries'
TARGET_TRAIN_SUMMARIES = 'target_train_summaries'
TARGET_TEST_SUMMARIES = 'target_test_summaries'
COMBINED_TRAIN_SUMMARIES = 'combined_train_summaries'
COMBINED_TEST_SUMMARIES = 'combined_test_summaries'

class GraphBuilder:
  '''
  Acts as a central place for building the Tensorflow graph, loading models and
  whatnot.
  When writing a new model, make sure the class name and filename
  match the convention of TestModel -> classname: TestModel,
                                        filename:  models/test_model.py
  If you want to keep it simple, just keep using FileModel and make a new YAML
  model definition in models/yaml_defs
  '''
  def __init__(self, model_name):
    self.model_name = model_name

    if not self._validate_model_name(self.model_name):
      msg = "Model \"" + self.model_name + "\" not supported."
      raise ValueError(msg)

    self.graph_nodes = None
    self.model_module = None

  def build_graph(self, only_test=False, build_placeholders=False):
    '''
    Build the Tensorflow graph if necessary, returning important graph nodes in
    a dict.
    '''
    if self.graph_nodes is not None:
      return self.graph_nodes

    self.graph_nodes = {}

    model_module = self._build_module()

    if build_placeholders:
      model_module.build_placeholders(Constants.config['num_way'], Constants.config['target_num_way'], self.template_grads_weights)
    # Input placeholders
    self.graph_nodes['images'] = tf.placeholder(tf.float32,
                                                      model_module.INPUT_SHAPE,
                                                      name='query_images')
    self.graph_nodes['global_step'] = tf.train.get_or_create_global_step()
    self.graph_nodes['is_training'] = tf.placeholder(tf.bool,
                                                     shape=[],
                                                     name='is_training')


    self.graph_nodes['outputs'] = model_module(self.graph_nodes['images'],
                                               graph_nodes=self.graph_nodes)
    self.graph_nodes['labels'] = model_module.get_target_tensors()
    self.graph_nodes['loss'] = model_module.get_loss(self.graph_nodes)

    if not only_test:
      with tf.control_dependencies(tf.get_collection(tf.GraphKeys.UPDATE_OPS)):
        opt = Optimizer.build_ops()
        self.graph_nodes['optimizer'] = opt
        grads = opt.compute_gradients(self.graph_nodes['loss'])
        self.graph_nodes['train_op'] = opt.apply_gradients(grads, global_step=self.graph_nodes['global_step'])



    
    self.graph_nodes['init_op'] = tf.group(tf.global_variables_initializer(),
                                           tf.local_variables_initializer())

    return self.graph_nodes, model_module


  def build_summary_ops(self):
    tf.summary.scalar('loss_source_train', self.graph_nodes['loss'], [SOURCE_TRAIN_SUMMARIES])
    tf.summary.scalar('loss_source_test', self.graph_nodes['loss'], [SOURCE_TEST_SUMMARIES])
    tf.summary.scalar('loss_target_train', self.graph_nodes['loss'], [TARGET_TRAIN_SUMMARIES])
    tf.summary.scalar('loss_target_test', self.graph_nodes['loss'], [TARGET_TEST_SUMMARIES])
    # predicted = tf.argmax(self.outputs, axis=1)
    def top_k(targets, predictions, k):
      the_val = tf.reduce_mean(tf.to_float(tf.nn.in_top_k(predictions, tf.to_int32(targets), k)))
      return the_val
    self.graph_nodes['top_1'] = top_k(self.graph_nodes['labels'], self.graph_nodes['outputs'], 1)
    tf.summary.scalar('source_train_top_1', self.graph_nodes['top_1'], [SOURCE_TRAIN_SUMMARIES])
    tf.summary.scalar('source_test_top_1', self.graph_nodes['top_1'], [SOURCE_TEST_SUMMARIES])
    tf.summary.scalar('target_train_top_1', self.graph_nodes['top_1'], [TARGET_TRAIN_SUMMARIES])
    tf.summary.scalar('target_test_top_1', self.graph_nodes['top_1'], [TARGET_TEST_SUMMARIES])
    tf.summary.scalar('combined_train_top_1', self.graph_nodes['top_1'], [COMBINED_TRAIN_SUMMARIES])
    tf.summary.scalar('combined_test_top_1', self.graph_nodes['top_1'], [COMBINED_TEST_SUMMARIES])

    self.graph_nodes['source_train_summary_op'] = tf.summary.merge_all(SOURCE_TRAIN_SUMMARIES)
    self.graph_nodes['source_test_summary_op'] = tf.summary.merge_all(SOURCE_TEST_SUMMARIES)
    self.graph_nodes['target_train_summary_op'] = tf.summary.merge_all(TARGET_TRAIN_SUMMARIES)
    self.graph_nodes['target_test_summary_op'] = tf.summary.merge_all(TARGET_TEST_SUMMARIES)
    self.graph_nodes['combined_train_summary_op'] = tf.summary.merge_all(COMBINED_TRAIN_SUMMARIES)
    self.graph_nodes['combined_test_summary_op'] = tf.summary.merge_all(COMBINED_TEST_SUMMARIES)


    # label_class = Helper.import_label_class(self.label_class_name)
    # for traintest in ['train', 'test']:
    #   for stat in label_class.TB_STATISTICS:
    #     Helper.register_tb_summary(traintest, stat)


  def _build_module(self):
    '''
    Import the model file/class and construct the Sonnet Module
    '''
    filename = Helper.class_to_filename(self.model_name)

    model_module = importlib.import_module('models.' + filename)
    model_class = getattr(model_module, self.model_name)
    self.model_module = model_class()

    return self.model_module

  def get_module(self):
    '''
    Get the Sonnet model module
    '''
    if self.model_module is None:
      self.model_module = self._build_module()
    return self.model_module

  def _validate_model_name(self, name):
    '''
    Check that a file exists corresponding to the given model class name
    e.g. MyCustomModel -> models/my_custom_model.py
    '''
    return os.path.isfile(os.path.abspath(os.path.join('models', Helper.class_to_filename(name) + '.py')))
