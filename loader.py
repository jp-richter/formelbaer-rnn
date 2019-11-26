import matplotlib.pyplot
import numpy

from dataset import Dataset
from torch.utils.data import DataLoader
from config import paths, config
from helper import store

import torch
import converter
import math
import os
import shutil
import generator
import datetime
import tokens
import ray
import helper

arxiv_dataset = None
oracle_dataset = None


def clear_directory(directory):
    """
    This function deletes all files in the synthetic data directory. The synthetic data directory serves as temporary
    store for data samples meant to be evaluated by the discriminating net. This function should be called after the
    evaluation or before the next evaluation to avoid evaluating the same data again.
    """

    shutil.rmtree(directory)
    os.makedirs(directory)


def save_pngs(samples, directory):
    """
    This function saves the given batch of samples produced by the generator to the given directory in the .png format.
    It also accepts lists of batches.

    :param samples: The samples that should be converted and saved. Needs to be a torch.Tensor of size (batch size,
        sequence length, one hot encoding length) or a list of such tensor objects.
    :param directory: The path to the directory to which the .png files will be written to.
    """

    converter.convert_to_png(samples, directory)


def save_sequences(samples, directory):
    """
    This function saves the sequences of integer ids for a given batch or list of sequences to the given directory. It
    is especially useful to see nodes of the syntax trees which will get ignored by the tree generation to assert
    their grammatical correctness. Also these integer id sequences allow to construct syntax trees whereas the saved
    png files only allow visual feedback of the generators performance. The sequences will be saved in text files as
    strings seperated by ',' f.e. 31,53,2,1 with every line representing a single sequence.

    :param samples: A batch in form of a tensor of size (batch size, sequence length, onehot encoding length) or a list
        of such tensors to save.
    :param directory: The path to the target directory the sequences.txt file will be written to.
    """

    with open(directory + '/sequences.txt', 'w') as f:

        sequences = []
        strings = []

        for sequence in samples:
            sequence_ids = []

            for onehot in sequence:
                sequence_ids.append(tokens.id(onehot))

            sequences.append(sequence_ids)
            strings.append(', '.join(str(s) for s in sequence_ids))

        all_sequences = '\n'.join(str(s) for s in sequences)
        f.write(all_sequences)


def make_directory_with_timestamp() -> str:
    """
    This function creates a directory named with the current time in the main app directory specified by the current
    configuration. This is useful to get unique directory names when saving experiment data, as the time stamp includes
    milliseconds.

    :return: The path to the directory created.
    """

    directory = paths.results + '/' + str(datetime.datetime.now())
    directory = directory.replace(':', '-').replace(' ', '-')[:-7]
    os.makedirs(directory)

    return directory


def make_dataset(directory, policy, label, num_batches) -> Dataset:
    """
    This function creates a Dataset of type dataset.Dataset with samples generated by the given generating net. The data
    gets stored in the given directory. Note that the dataset only saves image paths and not the images itsself. If the
    data gets removed the dataset becomes invalid.

    :param directory: The path to the directory in which the generated samples will be stored for the dataset.
    :param policy: The net generating the data samples for the dataset.
    :param label: The label for the generated data, should be equal to label_synth in configs. Can be None.
    :param num_batches: The amount of batches generated with the generator net.
    :return: Returns a dataset of type dataset.Dataset.
    """

    clear_directory(directory)
    sequences = generator.sample(policy, num_batches)
    save_pngs(sequences, directory)
    dataset = Dataset(directory, label)

    return dataset


def prepare_batch(batch) -> torch.Tensor:
    """
    This function prepares a batch of synthetic data and returns only a batch of images without a label. It stores the
    data in the synthetic data path of the script temporarily. It also deletes all contents of that directory
    beforehand. This function is useful to evaluate a single batch of sequences generated by the polcy net as the
    output fits as input to the discriminating net.

    :param batch: torch.Tensor of size (batch size, sequence length, input dimension) with sequences of onehot encodings
        to be converted to pngs and then loaded as image batch.
    :return: Returns a tensor of an image batch with size (batch size, 1, height, width).
    """

    clear_directory(paths.synthetic_data)
    save_pngs(batch, paths.synthetic_data)
    dataset = Dataset(paths.synthetic_data, config.label_synth, ordered=True)  # order critical
    loader = DataLoader(dataset, config.batch_size)
    images = next(iter(loader))[0]  # (images, labels)
    images = images.to(config.device)

    return images


def prepare_loader(num_samples, policy=None) -> DataLoader:
    """
    This function prepares a torch DataLoader for the arxiv data in the arxiv-samples directory. If a generator is
    provided, arxiv samples and synthetic samples generated by the generator will be mixed to equal amounts. In both
    samples the loader will hold num_samples of datapoints (image, label). The loader will be set to shuffle=True to
    make sure positive and negative samples do get mixed. Every time this function is called new arxiv samples will be
    loaded until the whole dataset has been iterated through.

    :param num_samples: The amount of samples the loader should hold.
    :param policy: The generator used to generate negative samples additionally to the arxiv data, if provided.
    :return: Returns a torch.util.DataLoader with shuffle=True.
    """

    dataset = Dataset()

    if policy is not None:
        num_batches = math.ceil((num_samples / config.batch_size) / 2)
        dataset = make_dataset(paths.synthetic_data, policy, config.label_synth, num_batches)

        arxiv_samples = arxiv_dataset.inorder(num_samples // 2)

    else:
        arxiv_samples = arxiv_dataset.inorder(num_samples)

    dataset.append(arxiv_samples)
    data_loader = DataLoader(dataset, config.batch_size, shuffle=True)

    return data_loader


def initialize():
    """
    This function sets up arxiv and oracle datasets dependant on the configurations. Ray gets initialized and the
    shared plasma object store will be created at paths.ray. All directories used by the script will be created here.
    Not calling this function at the beginning of the script will lead to errors.
    """

    global oracle_dataset, arxiv_dataset

    if not os.path.exists(paths.app):
        os.makedirs(paths.app)

    if not os.path.exists(paths.synthetic_data):
        os.makedirs(paths.synthetic_data)

    if not os.path.exists(paths.arxiv_data):
        raise ValueError('Provide training samples at ' + paths.arxiv_data + '.')

    if not os.path.exists(paths.dump):
        open(paths.dump, 'w+')

    if not os.path.exists(paths.ray_store):
        os.makedirs(paths.ray_store)

    if not os.path.exists(paths.results):
        os.makedirs(paths.results)

    if not os.path.exists(paths.log):
        open(paths.log, 'w')

    if not ray.is_initialized():
        with helper.HiddenPrints():
            if torch.cuda.is_available():
                ray.init(plasma_directory=paths.ray_store, memory=20000000000, object_store_memory=20000000000)
            else:
                ray.init(plasma_directory=paths.ray_store, memory=5000000000, object_store_memory=5000000000)

    arxiv_dataset = Dataset(paths.arxiv_data, label=config.label_real, recursive=True)


def finish(policy, discriminator):
    """
    This function creates a directory with the current timestamp at the application path set in the configurations.
    All experimental result data of a run such as weight parameters and log files will be saved. Additionally 100
    example images and sequences will be saved in this directory.

    :param policy: The policy net used in the experiment and for which the example data should be generated.
    :param discriminator: The discriminating net used in the experiment.
    """

    folder = store.folder

    policy.save(folder + '/policy-net.pt')
    discriminator.save(folder + '/discriminator-net.pt')

    save_policy_examples(folder, policy)

    for tag, value in [(t, v) for (t, v) in store if store.PLOTTABLE in store.attributes(t)]:
        path = '{}/{}'.format(folder, tag)
        plot_simple(path, value, tag, 'Steps', '', 'plot')

    for step, policy in enumerate(store.get('List: Mean Policies Per Generator Step')):
        path = '{}/policy_step_{}'.format(folder, step)
        plot_simple(path, policy, 'Generator Policy Step {}'.format(step), 'Tokens', 'Probabilities', 'bar')

    action_infos = store.get('List: Action Info Dicts')

    plot_action_infos(folder, action_infos)
    plot_action_deltas(folder, action_infos, 1)

    plot_action_infos(folder, action_infos, without_count=True)
    plot_action_deltas(folder, action_infos, 1, without_count=True)

    store.save()
    ray.shutdown()


def save_policy_examples(folder, policy):
    evaluation = generator.sample(policy, math.ceil(100 / config.batch_size))

    os.makedirs(folder + '/pngs')
    os.makedirs(folder + '/sequences')
    save_pngs(evaluation, folder + '/pngs')
    save_sequences(evaluation, folder + '/sequences')


def normalize(vector: list):
    vector = numpy.array(vector)

    if max(vector) - min(vector) == 0:
        return numpy.array([0.5] * len(vector))

    return (vector - min(vector)) / (max(vector) - min(vector))


def plot_simple(path, values, title, xlabel, ylabel, plot_type):
    figure, axis = matplotlib.pyplot.subplots()

    x = numpy.arange(0, len(values), 1)

    if plot_type == 'plot':
        axis.plot(x, values)
    elif plot_type == 'bar':
        axis.bar(x, values)

    axis.set_xlabel(xlabel)
    axis.set_ylabel(ylabel)

    matplotlib.pyplot.title(title)
    axis.grid()

    figure.savefig(path)


def plot_action_infos(folder, action_infos, without_count=False):
    path = '{}/action_infos_wo_count_{}'.format(folder, without_count)
    os.makedirs(path)

    for i, action_info in enumerate(action_infos):
        figure, axis = matplotlib.pyplot.subplots()

        x_pos = numpy.arange(0, len(action_info.keys()), 1)
        width = 0.9

        actions = action_info.keys()
        heights_counts = normalize([action_info[a][0] for a in actions])
        heights_probs = normalize([action_info[a][1] for a in actions])
        heights_reward = normalize([action_info[a][2] for a in actions])

        if not without_count:
            axis.bar(x_pos + width / 3, heights_counts, width / 3, label='Count')

        axis.bar(x_pos - width / 3, heights_reward, width / 3, label='Reward')
        axis.bar(x_pos, heights_probs, width / 3, label='Probability')

        ts = [tokens.get(i).name for i in actions]
        matplotlib.pyplot.xticks(x_pos, ts)
        axis.tick_params(axis='x', labelsize=8)

        matplotlib.pyplot.title('Actions In Step {}'.format(i))
        matplotlib.pyplot.legend(loc='best')
        matplotlib.pyplot.xticks(rotation='vertical')

        figure.set_size_inches(18, 8)
        figure.savefig('{}/step_{}.png'.format(path, i), bbox_inches="tight")


def plot_action_deltas(folder, action_infos, step_difference, without_count=False):
    path = '{}/action_changes_wo_count_{}'.format(folder, without_count)
    os.makedirs(path)

    count_last = [0] * tokens.count()
    prob_last = [0.0] * tokens.count()
    reward_last = [0.0] * tokens.count()

    for i, action_info in enumerate(action_infos):
        if i % step_difference == 0:

            count_deltas = [0] * tokens.count()
            prob_deltas = [0.0] * tokens.count()
            reward_deltas = [0.0] * tokens.count()

            for a in action_info.keys():
                count = action_info[a][0]
                prob = action_info[a][1]
                reward = action_info[a][2]

                count_deltas[a] = count - count_last[a]
                prob_deltas[a] = prob - prob_last[a]
                reward_deltas[a] = reward - reward_last[a]

            count_deltas = normalize(count_deltas)
            prob_deltas = normalize(prob_deltas)
            reward_deltas = normalize(reward_deltas)

            figure, axis = matplotlib.pyplot.subplots()

            x_pos = numpy.arange(0, tokens.count(), 1)
            width = 0.9

            if not without_count:
                axis.bar(x_pos - width / 3, count_deltas, width / 3, label='Count Delta')

            axis.bar(x_pos, prob_deltas, width / 3, label='Probability Delta')
            axis.bar(x_pos + width / 3, reward_deltas, width / 3, label='Reward Delta')

            ticks = [tokens.get(a).name for a in tokens.possibilities()]
            matplotlib.pyplot.xticks(x_pos, ticks)
            axis.tick_params(axis='x', labelsize=8)

            matplotlib.pyplot.title('Deltas Over {} Steps In Step {}'.format(step_difference, i))
            matplotlib.pyplot.legend(loc='best')
            matplotlib.pyplot.xticks(rotation='vertical')

            figure.set_size_inches(18, 8)
            figure.savefig('{}/step_{}.png'.format(path, i), bbox_inches="tight")