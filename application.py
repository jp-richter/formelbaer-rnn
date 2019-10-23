import config as cfg

import math
import torch
import generator
import discriminator
import loader
import log
import os
import converter
import multiprocessing


def generator_training(nn_policy, nn_rollout, nn_discriminator, nn_oracle, g_opt, o_crit) -> None:
    """
    The training loop of the generating policy net.

    :param nn_policy: The policy net that is the training target.
    :param nn_rollout: The rollout net that is used to complete unfinished sequences for estimation of rewards.
    :param nn_discriminator: The CNN that estimates the probability that the generated sequences represent the real
        data distribution, which serve as reward for the policy gradient training of the policy net.
    :param nn_oracle: A policy net which gets initialized with high variance parameters and serves as fake real
        distribution to analyze the performance of the model even when no comparisons to other models can be made.
    :param g_opt: The optimizer of the policy net.
    :param o_crit: The performance criterion for the oracle net.
    """

    nn_policy.train()
    nn_rollout.eval()

    for _ in range(cfg.app_cfg.g_steps):
        batch, hidden = nn_policy.initial()

        for length in range(cfg.app_cfg.seq_length):

            # generate a single next token given the sequences generated so far
            batch, hidden = generator.step(nn_policy, batch, hidden, nn_oracle, o_crit, save_prob=True)
            q_values = torch.empty([cfg.app_cfg.batchsize, 0])
            curr_length = batch.shape[1]

            if curr_length < cfg.app_cfg.seq_length:

                # estimate rewards for unfinished sequences with montecarlo trials
                for _ in range(cfg.app_cfg.montecarlo_trials):

                    # use the rollout policy to finish the sequences and collect the rewards
                    samples = generator.rollout(nn_rollout, batch, hidden)
                    samples = loader.load_single_batch(samples)
                    reward = discriminator.evaluate(nn_discriminator, samples)
                    q_values = torch.cat([q_values, reward], dim=1)

            else:

                # calculate reward for the finished sequence without montecarlo approximation
                samples = loader.load_single_batch(batch)
                reward = discriminator.evaluate(nn_discriminator, samples)
                q_values = torch.cat([q_values, reward], dim=1)

            # average the reward over all trials
            q_values = torch.mean(q_values, dim=1)
            nn_policy.reward_with(q_values)

        generator.update(nn_policy, g_opt)


def discriminator_training(nn_discriminator, nn_generator, d_opt, d_crit) -> None:
    """
    The training loop of the discriminator net.

    :param nn_generator: The policy net which generates the synthetic data the CNN gets trained to classify.
    :param nn_discriminator: The CNN that outputs an estimation of the probability that a given data point was generated
        by the policy network.
    :param d_opt: The optimizer of the CNN.
    :param d_crit: The performance criterion for the CNN.
    """

    nn_discriminator.train()
    nn_generator.eval()

    synthetic_data = generator.sample(nn_generator, cfg.app_cfg.d_steps)  # d steps * batch size samples
    torch_loader = loader.get_loader_mixed_with_positives(synthetic_data)

    for images, labels in torch_loader:
        discriminator.update(nn_discriminator, d_opt, d_crit, images, labels)


def adversarial_training() -> None:
    """
    The main loop of the script. To change parameters of the adversarial training parameters should not be changed here.
    Overwrite the configuration variables in config.py instead and start the adversarial training again.
    """

    # INITIALIZATION

    loader.make_directories()
    log.start_loading_data()
    converter.initialize_ray() # don't remove
    loader.load_data(log)
    log.finish_loading_data()

    nn_discriminator = discriminator.Discriminator()
    nn_policy = generator.Policy()
    nn_rollout = generator.Policy()
    nn_oracle = generator.Oracle()

    if cfg.app_cfg.oracle:
        nn_oracle.load(cfg.paths_cfg.oracle)

    d_opt = torch.optim.Adam(nn_discriminator.parameters(), lr=cfg.d_cfg.learnrate)
    d_crit = torch.nn.BCELoss()
    g_opt = torch.optim.Adam(nn_policy.parameters(), lr=cfg.g_cfg.learnrate)
    o_crit = torch.nn.KLDivLoss()

    # START ADVERSARIAL TRAINING

    log.start_experiment()

    for i in range(cfg.app_cfg.iterations):
        nn_rollout.set_parameters_to(nn_policy)

        discriminator_training(nn_discriminator, nn_rollout, d_opt, d_crit)
        generator_training(nn_policy, nn_rollout, nn_discriminator, nn_oracle, g_opt, o_crit)

        log.write(i + 1, nn_policy, nn_discriminator, nn_oracle, printout=True)

    # FINISH EXPERIMENT AND WRITE LOGS

    directory = loader.get_directory_with_timestamp()
    nn_policy.save(directory + '/policy-net.pt')
    nn_discriminator.save(directory + '/discriminator-net.pt')
    nn_oracle.save(directory + '/oracle-net.pt')

    log.finish_experiment(directory)

    evaluation = generator.sample(nn_policy, math.ceil(100 / cfg.app_cfg.batchsize))

    os.makedirs(directory + '/pngs')
    os.makedirs(directory + '/sequences')
    loader.save_pngs(evaluation, directory + '/pngs')
    loader.save_sequences(evaluation, directory + '/sequences')

    converter.shutdown_ray() # don't remove


def application() -> None:
    """
    Experimentational configurations can be defined here to overwrite the default configurations in config.py. Call
    adversarial_training() after each configuration definition. To start all defined experiments just run this script.
    Example:

    experiment = cfg.AppConfig(

        device=torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu'),

        iterations=2,
        d_steps=2,  # (*2) due to computational cost reasons
        g_steps=1,
        seq_length=2,  # 15
        montecarlo_trials=2,  # 15
        batchsize=multiprocessing.cpu_count(),  # computational cost reasons

        oracle=True,
        oracle_samplesize=100,

        label_synth=1,
        label_arxiv=0

    )

    cfg.app_cfg = experiment
    adversarial_training()
    """

    experiment = cfg.AppConfig(

        device=torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu'),

        iterations=2,
        d_steps=2,  # (*2) due to computational cost reasons
        g_steps=1,
        seq_length=2,  # 15
        montecarlo_trials=2,  # 15
        batchsize=multiprocessing.cpu_count(),  # computational cost reasons

        oracle=True,
        oracle_samplesize=100,

        label_synth=1,
        label_arxiv=0

    )

    cfg.app_cfg = experiment
    adversarial_training()


if __name__ == '__main__':
    application()
